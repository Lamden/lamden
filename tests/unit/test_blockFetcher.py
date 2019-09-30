from unittest import TestCase
from cilantro_ee.protocol.comm import services
from cilantro_ee.protocol.wallet import Wallet

from cilantro_ee.services.block_fetch import BlockFetcher
from cilantro_ee.services.block_server import BlockServer
from cilantro_ee.core.messages.message import Message
from cilantro_ee.core.messages.message_type import MessageType

from cilantro_ee.storage.master import CilantroStorageDriver

from cilantro_ee.core.top import TopBlockManager
import time
import zmq.asyncio
import zmq
import asyncio
import hashlib
from tests import random_txs


class FakeTopBlockManager:
    def __init__(self, height, hash_):
        self.height = height
        self.hash_ = hash_

    def get_latest_block_hash(self):
        return self.hash_

    def get_latest_block_number(self):
        return self.height


async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


class TestBlockFetcher(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.t = TopBlockManager()

    def tearDown(self):
        self.ctx.destroy()
        self.t.driver.flush()

    def test_get_latest_block_height(self):
        w = Wallet()
        m = BlockServer(socket_id=services._socket('tcp://127.0.0.1:10000'),
                        wallet=w,
                        ctx=self.ctx,
                        linger=500,
                        poll_timeout=100,
                        top=FakeTopBlockManager(101, 'abcd'))

        f = BlockFetcher(wallet=Wallet(), ctx=self.ctx)

        tasks = asyncio.gather(
            m.serve(),
            f.get_latest_block_height(services._socket('tcp://127.0.0.1:10000')),
            stop_server(m, 0.1),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        self.assertEqual(res[1], 101)

