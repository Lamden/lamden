from cilantro_ee.storage.vkbook import PhoneBook
from cilantro_ee.constants import conf
from cilantro_ee.protocol.overlay.network import Network
from cilantro_ee.constants.ports import DHT_PORT, EVENT_PORT
from cilantro_ee.logger.base import get_logger
from cilantro_ee.protocol.comm.services import AsyncInbox, SocketStruct
from cilantro_ee.core.messages.message import Message
from cilantro_ee.core.messages.message_type import MessageType
import zmq.asyncio
from cilantro_ee.protocol.wallet import Wallet
import time


class OverlayServer(AsyncInbox):
    def __init__(self, socket_id: SocketStruct, wallet: Wallet, ctx: zmq.Context, quorum, linger=2000, poll_timeout=2000):
        super().__init__(socket_id, wallet, ctx, linger, poll_timeout)

        self.network_address = 'tcp://{}:{}'.format(conf.HOST_IP, DHT_PORT)

        self.network = Network(wallet=self.wallet,
                               ctx=self.ctx,
                               ip=conf.HOST_IP,
                               peer_service_port=DHT_PORT,
                               event_publisher_port=EVENT_PORT,
                               bootnodes=conf.BOOTNODES,
                               initial_mn_quorum=PhoneBook.num_boot_masternodes,
                               initial_del_quorum=PhoneBook.num_boot_delegates,
                               mn_to_find=PhoneBook.masternodes,
                               del_to_find=PhoneBook.delegates)

        self.log = get_logger('Overlay.Server')
        if quorum <= 0:
            self.log.critical("quorum value should be greater than 0 for overlay server to properly synchronize!")

        self.quorum = quorum

    async def serve(self):
        await self.network.start()
        await super().serve()

    async def handle_msg(self, _id, msg):
        msg_type, msg, sender, timestamp, is_verified = Message.unpack_message_2(message=msg)
        if msg_type == MessageType.IP_FOR_VK_REQUEST:
            response = await self.network.find_node(vk_to_find=msg.vk.hex())
            reply = Message.get_signed_message_packed_2(wallet=self.wallet,
                                                        msg_type=MessageType.IP_FOR_VK_REPLY,
                                                        ip=response.encode())
            await self.return_msg(_id, reply)
        else:
            reply = Message.get_signed_message_packed_2(wallet=self.wallet,
                                                        msg_type=MessageType.BAD_REQUEST,
                                                        timestamp=int(time.time()))
            await self.return_msg(_id, reply)