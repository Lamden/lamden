import asyncio

from cilantro_ee.messages import MessageType, Message
from cilantro_ee.sockets.services import AsyncInbox
from cilantro_ee.storage import MetaDataStorage, VKBook


class BlockNotificationException(Exception):
    pass


class BlockNumberMismatch(BlockNotificationException):
    pass


class NotBlockNotificationMessageType(BlockNotificationException):
    pass


class NBNInbox(AsyncInbox):
    def __init__(self, contacts: VKBook, driver: MetaDataStorage=MetaDataStorage(), verify=True, *args, **kwargs):
        self.q = []
        self.contacts = contacts
        self.driver = driver
        self.verify = verify
        super().__init__(*args, **kwargs)

    async def handle_msg(self, _id, msg):
        if not self.verify:
            self.q.append(msg)
            return

        try:
            nbn = self.validate_nbn(msg)
            self.q.append(nbn)
        except BlockNotificationException:
            # This would be where the audit layer would take over
            pass

    def validate_nbn(self, msg):
        msg_type, msg_blob, _, _, _ = Message.unpack_message_2(msg)

        if msg_type != MessageType.BLOCK_NOTIFICATION:
            raise NotBlockNotificationMessageType

        if msg_blob.blockNum != self.driver.latest_block_num + 1:
            raise BlockNumberMismatch

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
