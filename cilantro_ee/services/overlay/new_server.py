from cilantro_ee.services.storage.vkbook import VKBook
from cilantro_ee.constants import conf
from cilantro_ee.services.overlay.network import Network
from cilantro_ee.constants.ports import DHT_PORT, EVENT_PORT
from cilantro_ee.core.logger.base import get_logger
from cilantro_ee.core.sockets.services import AsyncInbox, SocketStruct, get
from cilantro_ee.core.messages.message import Message
from cilantro_ee.core.messages.message_type import MessageType
import zmq.asyncio
from cilantro_ee.core.crypto.wallet import Wallet
import time


class OverlayServer(AsyncInbox):
    def __init__(self, socket_id: SocketStruct,
                 wallet: Wallet,
                 ctx: zmq.Context,
                 vkbook: VKBook,
                 ip=conf.HOST_IP,
                 peer_service_port=DHT_PORT,
                 event_publisher_port=EVENT_PORT,
                 bootnodes=conf.BOOTNODES,
                 linger=2000,
                 poll_timeout=2000):

        assert len(bootnodes) > 1, 'No bootnodes provided.'

        super().__init__(socket_id, wallet, ctx, linger, poll_timeout)

        self.vkbook = vkbook

        self.initial_mn_quorum = self.vkbook.masternode_quorum_min
        self.initial_del_quorum = self.vkbook.delegate_quorum_min
        self.mn_to_find = self.vkbook.masternodes
        self.del_to_find = self.vkbook.delegates

        self.network_address = 'tcp://{}:{}'.format(conf.HOST_IP, DHT_PORT)

        self.network = Network(wallet=self.wallet,
                               ctx=self.ctx,
                               ip=ip,
                               peer_service_port=peer_service_port,
                               event_publisher_port=event_publisher_port,
                               bootnodes=bootnodes,
                               initial_mn_quorum=self.initial_mn_quorum,
                               initial_del_quorum=self.initial_del_quorum,
                               mn_to_find=self.mn_to_find,
                               del_to_find=self.del_to_find)

        self.log = get_logger('Overlay.Server')

    async def serve(self):
        await self.network.start()
        await super().serve()

    async def return_bad_request(self, _id):
        reply = Message.get_signed_message_packed_2(wallet=self.wallet,
                                                    msg_type=MessageType.BAD_REQUEST,
                                                    timestamp=int(time.time()))
        await self.return_msg(_id, reply)

    async def handle_msg(self, _id, msg):
        print(msg)
        msg_type, msg, sender, timestamp, is_verified = Message.unpack_message_2(message=msg)
        if msg_type == MessageType.IP_FOR_VK_REQUEST:
            response = await self.network.find_node(vk_to_find=msg.vk.hex())

            ip = response.get(msg.vk.hex())
            if ip is not None:
                reply = Message.get_signed_message_packed_2(wallet=self.wallet,
                                                            msg_type=MessageType.IP_FOR_VK_REPLY,
                                                            ip=ip.encode())
                await self.return_msg(_id, reply)
            else:
                await self.return_bad_request(_id)
        else:
            await self.return_bad_request(_id)


class OverlayClient:
    def __init__(self, wallet: Wallet, ctx: zmq.Context, overlay_server_socket: SocketStruct):
        self.wallet = wallet
        self.ctx = ctx
        self.overlay_server_socket = overlay_server_socket

    async def get_ip_for_vk(self, vk: bytes):
        req = Message.get_signed_message_packed_2(wallet=self.wallet,
                                                  msg_type=MessageType.IP_FOR_VK_REQUEST,
                                                  vk=vk)

        resp = await get(self.overlay_server_socket, msg=req, ctx=self.ctx, dealer=True)

        if resp is not None:
            msg_type, msg, sender, timestamp, is_verified = Message.unpack_message_2(message=resp)

            return msg.ip.decode()
