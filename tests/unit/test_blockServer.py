from unittest import TestCase
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.block_server import BlockServer

from cilantro_ee.messages.message import Message
from cilantro_ee.messages.message_type import MessageType

from cilantro_ee.storage import CilantroStorageDriver, BlockchainDriver
from cilantro_ee import canonical
import time
import zmq.asyncio
import zmq
import asyncio
import secrets
from tests import random_txs


async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


class TestBlockServer(TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.t = BlockchainDriver()
        self.ctx = zmq.asyncio.Context()

    def tearDown(self):
        self.ctx.destroy()
        self.t.flush()
        self.loop.close()

    def test_get_latest_block_height(self):
        w = Wallet()
        m = BlockServer(w, 'tcp://127.0.0.1', self.ctx, linger=500, poll_timeout=500, driver=self.t)

        self.t.set_latest_block_num(555)

        async def get(msg):
            socket = self.ctx.socket(zmq.DEALER)
            socket.connect('tcp://127.0.0.1:10004')

            await socket.send(msg)

            res = await socket.recv()

            return res

        message = Message.get_signed_message_packed_2(wallet=w,
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

    def test_get_latest_block_hash(self):
        w = Wallet()
        m = BlockServer(w, 'tcp://127.0.0.1', self.ctx, linger=500, poll_timeout=500)

        self.t.set_latest_block_hash(b'\xAA' * 32)

        async def get(msg):
            socket = self.ctx.socket(zmq.DEALER)
            socket.connect('tcp://127.0.0.1:10004')

            await socket.send(msg)

            res = await socket.recv()

            return res

        message = Message.get_signed_message_packed_2(wallet=w,
                                                      msg_type=MessageType.LATEST_BLOCK_HASH_REQUEST,
                                                      timestamp=int(time.time()))

        tasks = asyncio.gather(
            m.serve(),
            get(message),
            stop_server(m, 0.2),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        msg_type, msg, sender, timestamp, is_verified = Message.unpack_message_2(res[1])

        self.assertEqual(msg.blockHash, b'\xAA' * 32)

    def test_get_block_blob_by_block_data_request(self):
        block = random_txs.random_block()
        w = Wallet()
        c = CilantroStorageDriver(key=w.sk.encode().hex())
        c.drop_collections()

        d = canonical.block_from_subblocks([s for s in block.subBlocks], previous_hash=b'x/00' * 32, block_num=0)

        d['blockOwners'] = [secrets.token_bytes(32) for _ in range(12)]

        c.put(d)

        del d['_id']
        del d['blockOwners']

        m = BlockServer(w, 'tcp://127.0.0.1', self.ctx, linger=500, poll_timeout=500, driver=c)

        async def get(msg):
            socket = self.ctx.socket(zmq.DEALER)
            socket.connect('tcp://127.0.0.1:10004')

            await socket.send(msg)

            res = await socket.recv()

            return res

        message = Message.get_signed_message_packed_2(wallet=w,
                                                      msg_type=MessageType.BLOCK_DATA_REQUEST,
                                                      blockNum=0)

        tasks = asyncio.gather(
            m.serve(),
            get(message),
            stop_server(m, 0.2),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        msg_type, msg, sender, timestamp, is_verified = Message.unpack_message_2(res[1])

        dd = canonical.block_from_subblocks([s for s in msg.subBlocks], previous_hash=b'x/00' * 32, block_num=0)

        self.assertDictEqual(d, dd)

    def test_get_block_blob_by_block_but_failure_returns_bad_request(self):
        w = Wallet()
        c = CilantroStorageDriver(key=w.sk.encode().hex())
        c.drop_collections()
        m = BlockServer(w, 'tcp://127.0.0.1', self.ctx, linger=500, poll_timeout=500, driver=c)

        async def get(msg):
            socket = self.ctx.socket(zmq.DEALER)
            socket.connect('tcp://127.0.0.1:10004')

            await socket.send(msg)

            res = await socket.recv()

            return res

        message = Message.get_signed_message_packed_2(wallet=w,
                                                      msg_type=MessageType.BLOCK_DATA_REQUEST,
                                                      blockNum=0)

        tasks = asyncio.gather(
            m.serve(),
            get(message),
            stop_server(m, 1),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        msg_type, msg, sender, timestamp, is_verified = Message.unpack_message_2(res[1])
        self.assertEqual(msg_type, MessageType.BAD_REQUEST)
