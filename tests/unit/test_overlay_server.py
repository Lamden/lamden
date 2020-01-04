from cilantro_ee.services.overlay.new_server import OverlayServer, OverlayClient
from unittest import TestCase
import zmq
import zmq.asyncio
from cilantro_ee.crypto import Wallet
import asyncio
from cilantro_ee.sockets.services import _socket, get
from cilantro_ee.messages.message import MessageType, Message
from cilantro_ee.contracts import sync
from cilantro_ee.services.storage.vkbook import VKBook


async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


class TestOverlayServer(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_serve(self):
        m, d = sync.get_masternodes_and_delegates_from_constitution()
        sync.submit_vkbook(
            {'masternodes': m, 'delegates': d, 'masternode_min_quorum': 1}, overwrite=True)

        w1 = Wallet()
        o = OverlayServer(
            socket_id=_socket('tcp://127.0.0.1:10999'),
            wallet=w1,
            ctx=self.ctx,
            ip='127.0.0.1',
            peer_service_port=10001,
            event_publisher_port=10002,
            bootnodes=['13.57.241.138', '52.53.252.151'],
            vkbook=VKBook(),
        )

        tasks = asyncio.gather(
            o.serve(),
            stop_server(o, 1)
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def test_find_node(self):
        w1 = Wallet()
        o = OverlayServer(
            socket_id=_socket('tcp://127.0.0.1:10999'),
            wallet=w1,
            ctx=self.ctx,
            ip='127.0.0.1',
            peer_service_port=10001,
            event_publisher_port=10002,
            bootnodes=[],
            mn_to_find=[],
            del_to_find=[],
            initial_mn_quorum=0,
            initial_del_quorum=0)

        w2 = Wallet()
        async def lazy_wait():
            await asyncio.sleep(5)

            req = Message.get_signed_message_packed_2(wallet=w2,
                                                      msg_type=MessageType.IP_FOR_VK_REQUEST,
                                                      vk=w1.vk.encode())

            resp = await get(_socket('tcp://127.0.0.1:10999'), msg=req, ctx=self.ctx, dealer=True)
            return resp

        tasks = asyncio.gather(
            o.serve(),
            lazy_wait(),
            stop_server(o, 6)
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        msg_got = res[1]
        msg_type, msg, sender, timestamp, is_verified = Message.unpack_message_2(message=msg_got)

        self.assertEqual(msg.ip.decode(), '127.0.0.1')


class TestOverlayClient(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_get_ip_for_vk_works(self):
        w1 = Wallet()
        o = OverlayServer(
            socket_id=_socket('tcp://127.0.0.1:10999'),
            wallet=w1,
            ctx=self.ctx,
            ip='127.0.0.1',
            peer_service_port=10001,
            event_publisher_port=10002,
            bootnodes=[],
            mn_to_find=[],
            del_to_find=[],
            initial_mn_quorum=0,
            initial_del_quorum=0)

        w2 = Wallet()
        c = OverlayClient(wallet=w2, ctx=self.ctx, overlay_server_socket=_socket('tcp://127.0.0.1:10999'))

        async def lazy_wait():
            await asyncio.sleep(5)
            return await c.get_ip_for_vk(w1.vk.encode())

        tasks = asyncio.gather(
            o.serve(),
            lazy_wait(),
            stop_server(o, 6)
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        msg = res[1]

        self.assertEqual(msg, '127.0.0.1')
