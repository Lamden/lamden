import cilantro_ee.sockets.inbox
import cilantro_ee.sockets.struct
from cilantro_ee.sockets import services
import zmq.asyncio
from cilantro_ee.crypto.wallet import Wallet
from unittest import TestCase
import asyncio


async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


class TestAsyncServer(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()

    def test_init(self):
        w = Wallet()
        cilantro_ee.sockets.inbox.AsyncInbox(cilantro_ee.sockets.struct._socket('tcp://127.0.0.1:10000'), self.ctx)

    def test_addresses_correct(self):
        w = Wallet()
        m = cilantro_ee.sockets.inbox.AsyncInbox(cilantro_ee.sockets.struct._socket('tcp://127.0.0.1:10000'), self.ctx)

        self.assertEqual(m.address, 'tcp://*:10000')

    def test_sockets_are_initially_none(self):
        w = Wallet()
        m = cilantro_ee.sockets.inbox.AsyncInbox(cilantro_ee.sockets.struct._socket('tcp://127.0.0.1:10000'), self.ctx)

        self.assertIsNone(m.socket)

    def test_setup_frontend_creates_socket(self):
        w = Wallet()
        m = cilantro_ee.sockets.inbox.AsyncInbox(cilantro_ee.sockets.struct._socket('tcp://127.0.0.1:10000'), self.ctx)
        m.setup_socket()

        self.assertEqual(m.socket.type, zmq.ROUTER)
        self.assertEqual(m.socket.getsockopt(zmq.LINGER), m.linger)

    def test_sending_message_returns_it(self):
        w = Wallet()
        m = cilantro_ee.sockets.inbox.AsyncInbox(cilantro_ee.sockets.struct._socket('tcp://127.0.0.1:10000'), self.ctx, linger=500, poll_timeout=500)

        async def get(msg):
            socket = self.ctx.socket(zmq.DEALER)
            socket.connect('tcp://127.0.0.1:10000')

            await socket.send(msg)

            res = await socket.recv()

            return res

        tasks = asyncio.gather(
            m.serve(),
            get(b'howdy'),
            stop_server(m, 0.2),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        self.assertEqual(res[1], b'howdy')
