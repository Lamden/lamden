from unittest import TestCase
from cilantro_ee.protocol.comm import services
from cilantro_ee.protocol.wallet import Wallet
from cilantro_ee.protocol import wallet
from cilantro_ee.services.block_server import BlockServer

from cilantro_ee.core.messages.message import Message
from cilantro_ee.core.messages.message_type import MessageType

import zmq.asyncio
import zmq
import asyncio
import json

async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


class TestBlockServer(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()

    def tearDown(self):
        self.ctx.destroy()

    def test_sending_message_returns_it(self):
        w = Wallet()
        m = BlockServer(services._socket('tcp://127.0.0.1:10000'), w, self.ctx, linger=500, poll_timeout=500)

        async def get(msg):
            socket = self.ctx.socket(zmq.DEALER)
            socket.connect('tcp://127.0.0.1:10000')

            await socket.send(b'0'+msg[1])

            res = await socket.recv()

            return res

        message = Message.get_signed_message_packed(signee=w.sk.encode(), msg_type=MessageType.BLOCK_DATA_REQUEST, blockNum=100, sign=wallet.sign)
        print(message)

        tasks = asyncio.gather(
            m.serve(),
            get(message),
            stop_server(m, 0.2),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        self.assertEqual(res[1], b'howdy')
