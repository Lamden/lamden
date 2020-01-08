import asyncio
import hashlib

from cilantro_ee.crypto.transaction import transaction_is_valid, TransactionException
from cilantro_ee.crypto.wallet import _verify
from cilantro_ee.messages.message import Message
from cilantro_ee.messages.message_type import MessageType
from cilantro_ee.core.nonces import NonceManager
from cilantro_ee.sockets.services import AsyncInbox
from cilantro_ee.storage.vkbook import VKBook


class DelegateWorkInboxException(Exception):
    pass


class NotTransactionBatchMessageType(DelegateWorkInboxException):
    pass


class ReceivedInvalidWork(DelegateWorkInboxException):
    pass


class InvalidSignature(DelegateWorkInboxException):
    pass


class WorkInbox(AsyncInbox):
    def __init__(self, contacts: VKBook, nonces: NonceManager=NonceManager(), verify=True, *args, **kwargs):
        self.work = {}

        self.contacts = contacts
        self.nonces = nonces
        self.current_masternodes = self.contacts.masternodes
        self.verify = verify

        super().__init__(*args, **kwargs)

    async def handle_msg(self, _id, msg):
        if not self.verify:
            msg_type, msg_blob, _, _, _ = Message.unpack_message_2(msg)
            self.work[msg_blob.sender.hex()] = msg_blob

        try:
            msg_struct = self.verify_transaction_bag(msg)
            self.work[msg_struct.sender.hex()] = msg_struct
        except DelegateWorkInboxException:
            # Audit trigger
            pass

    def verify_transaction_bag(self, msg):
        msg_type, msg_blob, _, _, _ = Message.unpack_message_2(msg)

        if msg_type != MessageType.TRANSACTION_BATCH:
            raise NotTransactionBatchMessageType

        # Set up a hasher for input hash and a list for valid txs
        h = hashlib.sha3_256()

        for tx in msg_blob.transactions:
            # Double check to make sure all transactions are valid
            try:
                transaction_is_valid(tx=tx,
                                     expected_processor=msg_blob.sender,
                                     driver=self.nonces,
                                     strict=False)
            except TransactionException as e:
                raise DelegateWorkInboxException

            h.update(tx.as_builder().to_bytes_packed())

        h.update('{}'.format(msg_blob.timestamp).encode())
        input_hash = h.digest()
        if input_hash != msg_blob.inputHash or \
           not _verify(msg_blob.sender, h.digest(), msg_blob.signature):
            raise InvalidSignature

        return msg_blob

    async def wait_for_next_batch_of_work(self):
        self.work.clear()
        self.current_masternodes = self.contacts.masternodes
        # Wait for work from all masternodes that are currently online
        # How do we test if they are online? idk.
        while len(set(self.current_masternodes) - set(self.work.keys())) > 0:
            await asyncio.sleep(0)

        return self.work
