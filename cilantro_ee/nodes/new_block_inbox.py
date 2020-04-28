import asyncio

from cilantro_ee.messages import MessageType, Message
from cilantro_ee.sockets.inbox import AsyncInbox, SecureAsyncInbox
from cilantro_ee.storage import BlockchainDriver, VKBook
from cilantro_ee.logger.base import get_logger
import math


class BlockNotificationException(Exception):
    pass


class BlockNumberMismatch(BlockNotificationException):
    pass


class NotBlockNotificationMessageType(BlockNotificationException):
    pass


class BadConsensusBlock(BlockNotificationException):
    pass


class NBNInbox(SecureAsyncInbox):
    def __init__(self, contacts: VKBook, driver: BlockchainDriver=BlockchainDriver(), verify=True, allow_current_block_num=False, *args, **kwargs):
        self.q = []
        self.contacts = contacts
        self.driver = driver
        self.verify = verify
        self.quorum_ratio = 0.50
        self.allow_current_block_num = allow_current_block_num
        self.log = get_logger('NBN')
        self.signers = len(self.contacts.delegates) # This has to be updated every block in case a delegate is added or removed
        super().__init__(*args, **kwargs)

    async def handle_msg(self, _id, msg):
        if not self.verify:
            self.q.append(msg)
            return

        try:
            nbn = self.validate_nbn(msg)
            self.log.info(nbn)
            self.q.append(nbn)
        except BlockNotificationException as e:
            # This would be where the audit layer would take over
            self.log.error(type(e))

    def validate_nbn(self, msg):
        msg_type, msg_blob, _, _, _ = Message.unpack_message_2(msg)

        if msg_type != MessageType.BLOCK_DATA:
            raise NotBlockNotificationMessageType

        #if msg_blob.blockNum != self.driver.latest_block_num + 1:
        #    raise BlockNumberMismatch

        # Check if signed by quorum amount
        for sub_block in msg_blob.subBlocks:
            if len(sub_block.signatures) < math.ceil(self.signers * self.quorum_ratio):
                raise BadConsensusBlock

        # Deserialize off the socket
        return msg_blob.to_dict()

    async def wait_for_next_nbn(self):
        while len(self.q) <= 0:
            await asyncio.sleep(0)

        nbn = self.q.pop(0)
        if nbn['blockNum'] < self.driver.latest_block_num:
            self.log.error('you found it')

        self.q.clear()

        return nbn

    def clean(self):
        self.q = [nbn for nbn in self.q if nbn['blockNum'] >= self.driver.latest_block_num]

    def update_signers(self):
        self.signers = len(self.contacts.delegates)
