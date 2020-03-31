import asyncio
import hashlib

from cilantro_ee.crypto.transaction import transaction_is_valid, TransactionException
from cilantro_ee.crypto.wallet import _verify
from cilantro_ee.messages.message import Message
from cilantro_ee.messages.message_type import MessageType
from cilantro_ee.storage import BlockchainDriver
from cilantro_ee.sockets.inbox import AsyncInbox, SecureAsyncInbox
from cilantro_ee.storage.vkbook import VKBook
from cilantro_ee.crypto.transaction_batch import transaction_list_to_transaction_batch

from cilantro_ee.logger.base import get_logger
import logging

import time

from copy import deepcopy


class DelegateWorkInboxException(Exception):
    pass


class NotTransactionBatchMessageType(DelegateWorkInboxException):
    pass


class ReceivedInvalidWork(DelegateWorkInboxException):
    pass


class InvalidSignature(DelegateWorkInboxException):
    pass


class NotMasternode(DelegateWorkInboxException):
    pass


class WorkInbox(SecureAsyncInbox):
    def __init__(self, contacts, driver: BlockchainDriver=BlockchainDriver(), verify=True, debug=True, *args, **kwargs):
        self.work = {}

        self.driver = driver
        self.current_contacts = contacts
        self.verify = verify

        self.todo = []
        self.accepting_work = False

        self.log = get_logger('DEL WI')
        self.log.propagate = debug

        super().__init__(*args, **kwargs)

    async def handle_msg(self, _id, msg):
        self.log.info('Got some work.')
        await self.return_msg(_id, b'ok')
        #asyncio.ensure_future(self.return_msg(_id, b'ok'))

        if not self.accepting_work:
            self.log.info('TODO')
            self.todo.append(msg)

        else:
            self.verify_work(msg)

    def verify_work(self, msg):
        if not self.verify:
            msg_type, msg_blob, _, _, _ = Message.unpack_message_2(msg)
            self.work[msg_blob.sender.hex()] = msg_blob
        try:
            msg_struct = self.verify_transaction_bag(msg)
            self.work[msg_struct.sender.hex()] = msg_struct
            self.log.info(msg_struct.sender.hex())
        except DelegateWorkInboxException as e:
            # Audit trigger
            self.log.error(type(e))
        except TransactionException as e:
            self.log.error(type(e))

    def verify_transaction_bag(self, msg):
        # What is the valid signature
        msg_type, msg_blob, _, _, _ = Message.unpack_message_2(msg)

        self.log.info(f'{len(msg_blob.transactions)} transactions of work')

        if msg_type != MessageType.TRANSACTION_BATCH:
            raise NotTransactionBatchMessageType

        if msg_blob.sender.hex() not in self.current_contacts:
            raise NotMasternode

        # Set up a hasher for input hash and a list for valid txs
        h = hashlib.sha3_256()

        for tx in msg_blob.transactions:
            # Double check to make sure all transactions are valid
            try:
                transaction_is_valid(tx=tx,
                                     expected_processor=msg_blob.sender,
                                     driver=self.driver,
                                     strict=False)
            except TransactionException as e:
                self.log.error(tx)
                raise e

            h.update(tx.as_builder().to_bytes_packed())

        h.update('{}'.format(msg_blob.timestamp).encode())
        input_hash = h.digest().hex()
        if input_hash != msg_blob.inputHash or \
           not _verify(msg_blob.sender, h.digest(), msg_blob.signature):
            raise InvalidSignature

        return msg_blob

    async def wait_for_next_batch_of_work(self, current_contacts, timeout=1000):
        self.accepting_work = True
        self.current_contacts = current_contacts

        self.log.info(f'Current todo {self.todo}')

        for work in self.todo:
            self.verify_work(work)

        self.todo.clear()

        # Wait for work from all masternodes that are currently online
        # start = time.time() * 1000
        while len(set(current_contacts) - set(self.work.keys())) > 0:
            await asyncio.sleep(0)
            self.log.info('Waiting for work...')

        # If timeout is hit, just pad the rest of the expected amounts with empty tx batches?
        for masternode in set(current_contacts) - set(self.work.keys()):
            self.work[masternode] = transaction_list_to_transaction_batch([], wallet=self.wallet)

        self.accepting_work = False

        returned_work = deepcopy(list(self.work.values()))
        self.work.clear()

        return returned_work
