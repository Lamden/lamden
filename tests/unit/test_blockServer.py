from unittest import TestCase
from cilantro_ee.protocol.comm import services
from cilantro_ee.protocol.wallet import Wallet
from cilantro_ee.protocol import wallet
from cilantro_ee.services.block_server import BlockServer

from cilantro_ee.core.messages.message import Message
from cilantro_ee.core.messages.message_type import MessageType

from cilantro_ee.core.top import TopBlockManager
import time
import zmq.asyncio
import zmq
import asyncio
import json
import struct

async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


class TestBlockServer(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.t = TopBlockManager()

    def tearDown(self):
        self.ctx.destroy()
        self.t.driver.flush()

    def test_sending_message_returns_it(self):
        w = Wallet()
        m = BlockServer(services._socket('tcp://127.0.0.1:10000'), w, self.ctx, linger=500, poll_timeout=500)

        self.t.set_latest_block_number(555)

        async def get(msg):
            socket = self.ctx.socket(zmq.DEALER)
            socket.connect('tcp://127.0.0.1:10000')

            await socket.send(msg)

            res = await socket.recv()

            return res

        message = Message.get_signed_message_packed_2(sk=w.sk.encode(),
                                                      msg_type=MessageType.LATEST_BLOCK_HEIGHT_REQUEST,
                                                      timestamp=int(time.time()))

        tasks = asyncio.gather(
            m.serve(),
            get(message),
            stop_server(m, 0.2),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        msg_type, msg, sender, timestamp, is_verified = Message.unpack_message_2(res[1])

        self.assertEqual(msg.blockHeight, 555)
