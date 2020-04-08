import asyncio
import hashlib

from cilantro_ee.crypto.transaction import transaction_is_valid, TransactionException
from cilantro_ee.crypto.transaction_batch import transaction_batch_is_valid
from cilantro_ee.crypto.wallet import _verify
from cilantro_ee.messages.message import Message
from cilantro_ee.messages.message_type import MessageType
from cilantro_ee.storage import BlockchainDriver
from cilantro_ee.sockets.inbox import SecureAsyncInbox

from cilantro_ee.logger.base import get_logger

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
    def __init__(self, parameters, driver: BlockchainDriver=BlockchainDriver(), verify=True, debug=True, *args, **kwargs):
        self.work = {}

        self.q = []

        self.driver = driver
        self.verify = verify

        self.parameters = parameters

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
            self.q.append(msg)

    def verify_work(self, msg):
        if not self.verify:
            msg_type, msg_blob, _, _, _ = Message.unpack_message_2(msg)
            self.work[msg_blob.sender.hex()] = msg_blob
        try:
            msg_type, msg_blob, _, _, _ = Message.unpack_message_2(msg)

            self.log.info(f'{len(msg_blob.transactions)} transactions of work')

            if msg_type != MessageType.TRANSACTION_BATCH:
                raise NotTransactionBatchMessageType

            transaction_batch_is_valid(
                tx_batch=msg_blob,
                current_masternodes=self.parameters.get_masternode_vks(),
                driver=self.driver
            )

            self.work[msg_blob.sender.hex()] = msg_blob
            self.log.info(msg_blob.sender.hex())

        except DelegateWorkInboxException as e:
            # Audit trigger. Won't prevent operation of the network. Shim will be used.
            self.log.error(type(e))
        except TransactionException as e:
            self.log.error(type(e))

    def process_todo_work(self):
        self.log.info(f'Current todo {self.todo}')

        for work in self.todo:
            self.verify_work(work)

        self.todo.clear()

    async def wait_for_next_batch_of_work(self, seconds_to_timeout=5):
        # Wait for work from all masternodes that are currently online
        start = None
        timeout_timer = False
        self.log.info(f'{set(self.work.keys())} / {len(set(self.parameters.get_masternode_vks()))} work bags received')
        while len(set(self.parameters.get_masternode_vks()) - set(self.work.keys())) > 0:
            await asyncio.sleep(0)

            if len(set(self.work.keys())) > 0 and not timeout_timer:
                # Got one, start the timeout timer
                timeout_timer = True
                start = time.time()

            if timeout_timer:
                now = time.time()
                if now - start > seconds_to_timeout:
                    self.log.error('TIMEOUT')
                    break

        returned_work = deepcopy(list(self.work.values()))
        self.work.clear()

        return returned_work
