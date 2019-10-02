from cilantro_ee.protocol.overlay.new_server import OverlayServer
from unittest import TestCase
import zmq
import zmq.asyncio
from cilantro_ee.protocol.wallet import Wallet
import asyncio
from cilantro_ee.protocol.comm.services import _socket


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

        tasks = asyncio.gather(
            o.serve(),
            stop_server(o, 1)
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)
