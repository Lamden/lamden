import asyncio

from cilantro_ee.messages import MessageType, Message
from cilantro_ee.sockets.services import AsyncInbox
from cilantro_ee.storage import MetaDataStorage, VKBook

import math


class BlockNotificationException(Exception):
    pass


class BlockNumberMismatch(BlockNotificationException):
    pass


class NotBlockNotificationMessageType(BlockNotificationException):
    pass


class BadConsensusBlock(BlockNotificationException):
    pass


class NBNInbox(AsyncInbox):
    def __init__(self, contacts: VKBook, driver: MetaDataStorage=MetaDataStorage(), verify=True, *args, **kwargs):
        self.q = []
        self.contacts = contacts
        self.driver = driver
        self.verify = verify
        self.quorum_ratio = 0.66
        super().__init__(*args, **kwargs)

    async def handle_msg(self, _id, msg):
        if not self.verify:
            self.q.append(msg)
            return

        print('got msg')

        try:
            nbn = self.validate_nbn(msg)
            self.q.append(nbn)
        except BlockNotificationException as e:
            # This would be where the audit layer would take over
            print(type(e))
            pass

    def validate_nbn(self, msg):
        msg_type, msg_blob, _, _, _ = Message.unpack_message_2(msg)

        print(msg_blob)

        if msg_type != MessageType.BLOCK_DATA:
            raise NotBlockNotificationMessageType

        if msg_blob.blockNum != self.driver.latest_block_num + 1:
            raise BlockNumberMismatch

        # Check if signed by quorum amount
        for sub_block in msg_blob.subBlocks:
            if len(sub_block.signatures) < math.ceil(len(self.contacts.delegates) * self.quorum_ratio):
                raise BadConsensusBlock

        # Deserialize off the socket
        return msg_blob.to_dict()

    async def wait_for_next_nbn(self):
        while len(self.q) <= 0:
            await asyncio.sleep(0)

        nbn = self.q.pop(0)
        self.q.clear()

        return nbn

    def clean(self):
        self.q = [nbn for nbn in self.q if nbn['blockNum'] == self.driver.latest_block_num + 1]
