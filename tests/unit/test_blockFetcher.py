from unittest import TestCase
from cilantro_ee.core.sockets import services
from cilantro_ee.core.crypto.wallet import Wallet

from cilantro_ee.services.block_fetch import BlockFetcher
from cilantro_ee.services.block_server import BlockServer
from cilantro_ee.core.messages.message import Message
from cilantro_ee.core.messages.message_type import MessageType
from cilantro_ee.core import canonical
import secrets
from cilantro_ee.services.storage.master import CilantroStorageDriver

from cilantro_ee.core.top import TopBlockManager
from cilantro_ee.core.sockets.socket_book import SocketBook

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


class FakeSocketBook:
    def __init__(self, network=None, phonebook_function: callable = None):
        self.network = network
        self.phonebook_function = phonebook_function
        self.sockets = {}

    async def refresh(self):
        self.sockets = self.phonebook_function()


class FakeBlockDriver:
    def __init__(self, block_dict):
        self.block_dict = block_dict

    def get_block(self, i):
        return self.block_dict

class FakeBlockReciever:
    def __init__(self):
        self.blocks = {}

    def put(self, d):
        self.blocks[d['blockNum']] = d

async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


async def pause(f, time):
    await asyncio.sleep(time)
    return await f()


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

    def test_get_consensus_on_block_height(self):
        w1 = Wallet()
        m1 = BlockServer(socket_id=services._socket('tcp://127.0.0.1:10000'),
                         wallet=w1,
                         ctx=self.ctx,
                         linger=500,
                         poll_timeout=100,
                         top=FakeTopBlockManager(101, 'abcd'))

        w2 = Wallet()
        m2 = BlockServer(socket_id=services._socket('tcp://127.0.0.1:10001'),
                         wallet=w2,
                         ctx=self.ctx,
                         linger=500,
                         poll_timeout=100,
                         top=FakeTopBlockManager(101, 'abcd'))

        w3 = Wallet()
        m3 = BlockServer(socket_id=services._socket('tcp://127.0.0.1:10002'),
                         wallet=w3,
                         ctx=self.ctx,
                         linger=500,
                         poll_timeout=100,
                         top=FakeTopBlockManager(101, 'abcd'))

        w4 = Wallet()
        m4 = BlockServer(socket_id=services._socket('tcp://127.0.0.1:10003'),
                         wallet=w4,
                         ctx=self.ctx,
                         linger=500,
                         poll_timeout=100,
                         top=FakeTopBlockManager(90, 'abcd'))

        def get_sockets():
            return {
                'a': services._socket('tcp://127.0.0.1:10000'),
                'b': services._socket('tcp://127.0.0.1:10001'),
                'c': services._socket('tcp://127.0.0.1:10002'),
                'd': services._socket('tcp://127.0.0.1:10003'),
            }

        sock_book = FakeSocketBook(None, get_sockets)

        f = BlockFetcher(wallet=Wallet(), ctx=self.ctx, masternode_sockets=sock_book)

        tasks = asyncio.gather(
            m1.serve(),
            m2.serve(),
            m3.serve(),
            m4.serve(),
            f.find_missing_block_indexes(),
            stop_server(m1, 0.1),
            stop_server(m2, 0.1),
            stop_server(m3, 0.1),
            stop_server(m4, 0.1),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        self.assertEqual(res[4], 101)

    def store_blocks(self, c, i, initial_hash=b'\x00' * 32):
        current_hash = initial_hash
        for _i in range(i):
            block = random_txs.random_block(block_num=_i)
            d = canonical.block_from_subblocks([s for s in block.subBlocks], previous_hash=current_hash, block_num=_i)

            d['blockOwners'] = [secrets.token_bytes(32) for _ in range(12)]

            c.put(d)

            del d['_id']
            del d['blockOwners']

            current_hash = d['blockHash']

    def test_fetch_block_from_master(self):
        # Setup Mongo
        w = Wallet()
        c = CilantroStorageDriver(key=w.sk.encode())
        c.drop_collections()

        # Store 20 blocks
        self.store_blocks(c, 1)

        w1 = Wallet()
        m1 = BlockServer(socket_id=services._socket('tcp://127.0.0.1:10000'),
                         wallet=w1,
                         ctx=self.ctx,
                         linger=500,
                         poll_timeout=100,
                         top=FakeTopBlockManager(101, 'abcd'),
                         driver=c)

        def get_sockets():
            return {
                'a': services._socket('tcp://127.0.0.1:10000'),
            }

        sock_book = FakeSocketBook(None, get_sockets)

        f = BlockFetcher(wallet=Wallet(), ctx=self.ctx, masternode_sockets=sock_book)

        tasks = asyncio.gather(
            m1.serve(),
            f.get_block_from_master(0, services._socket('tcp://127.0.0.1:10000')),
            stop_server(m1, 0.3),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        block_dict = c.get_block(0)

        del block_dict['blockOwners']

        got_block = res[1]

        got = canonical.block_from_subblocks([s for s in got_block.subBlocks], previous_hash=b'\x00' * 32, block_num=0)

        self.assertDictEqual(block_dict, got)

    def test_fetch_block_from_multiple_masters_where_some_are_corrupted(self):
        w = Wallet()
        c = CilantroStorageDriver(key=w.sk.encode())
        c.drop_collections()

        # Store 20 blocks
        self.store_blocks(c, 1)

        # Good one
        w1 = Wallet()
        m1 = BlockServer(socket_id=services._socket('tcp://127.0.0.1:10000'),
                         wallet=w1,
                         ctx=self.ctx,
                         linger=500,
                         poll_timeout=100,
                         top=FakeTopBlockManager(101, 'abcd'),
                         driver=c)

        # Bad Ones
        bad_block = canonical.block_from_subblocks([s for s in random_txs.random_block().subBlocks],
                                                   previous_hash=b'\x01' * 32,
                                                   block_num=0)

        bad_block['blockOwners'] = [secrets.token_bytes(32) for _ in range(30)]

        d = FakeBlockDriver(bad_block)
        w2 = Wallet()
        m2 = BlockServer(socket_id=services._socket('tcp://127.0.0.1:10001'),
                         wallet=w2,
                         ctx=self.ctx,
                         linger=500,
                         poll_timeout=100,
                         top=FakeTopBlockManager(101, 'abcd'),
                         driver=d)

        w3 = Wallet()
        m3 = BlockServer(socket_id=services._socket('tcp://127.0.0.1:10002'),
                         wallet=w3,
                         ctx=self.ctx,
                         linger=500,
                         poll_timeout=100,
                         top=FakeTopBlockManager(101, 'abcd'),
                         driver=d)

        def get_sockets():
            return {
                'b': services._socket('tcp://127.0.0.1:10001'),
                'c': services._socket('tcp://127.0.0.1:10002'),
                'a': services._socket('tcp://127.0.0.1:10000'),
            }

        sock_book = FakeSocketBook(None, get_sockets)
        f = BlockFetcher(wallet=Wallet(), ctx=self.ctx, masternode_sockets=sock_book)

        tasks = asyncio.gather(
            m1.serve(),
            m2.serve(),
            m3.serve(),
            f.find_valid_block(0, latest_hash=b'\x00' * 32, timeout=3000),
            stop_server(m1, 0.7),
            stop_server(m2, 0.7),
            stop_server(m3, 0.7),
        )

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        block_dict = c.get_block(0)

        del block_dict['blockOwners']

        got_block = res[3]

        got = canonical.block_from_subblocks([s for s in got_block.subBlocks], previous_hash=b'\x00' * 32, block_num=0)

        self.assertDictEqual(block_dict, got)

    def test_fetch_multiple_blocks_works_with_good_actors(self):
        w = Wallet()
        c = CilantroStorageDriver(key=w.sk.encode())
        c.drop_collections()

        # Store 20 blocks
        self.store_blocks(c, 10)

        # Good one
        w1 = Wallet()
        m1 = BlockServer(socket_id=services._socket('tcp://127.0.0.1:10000'),
                         wallet=w1,
                         ctx=self.ctx,
                         linger=500,
                         poll_timeout=100,
                         top=FakeTopBlockManager(101, 'abcd'),
                         driver=c)

        w2 = Wallet()
        m2 = BlockServer(socket_id=services._socket('tcp://127.0.0.1:10001'),
                         wallet=w2,
                         ctx=self.ctx,
                         linger=500,
                         poll_timeout=100,
                         top=FakeTopBlockManager(101, 'abcd'),
                         driver=c)

        w3 = Wallet()
        m3 = BlockServer(socket_id=services._socket('tcp://127.0.0.1:10002'),
                         wallet=w3,
                         ctx=self.ctx,
                         linger=500,
                         poll_timeout=100,
                         top=FakeTopBlockManager(101, 'abcd'),
                         driver=c)

        def get_sockets():
            return {
                'b': services._socket('tcp://127.0.0.1:10001'),
                'c': services._socket('tcp://127.0.0.1:10002'),
                'a': services._socket('tcp://127.0.0.1:10000'),
            }

        sock_book = FakeSocketBook(None, get_sockets)
        fake_driver = FakeBlockReciever()
        f = BlockFetcher(wallet=Wallet(), ctx=self.ctx, masternode_sockets=sock_book, blocks=fake_driver)

        tasks = asyncio.gather(
            m1.serve(),
            m2.serve(),
            m3.serve(),
            f.fetch_blocks(latest_block_available=9),
            stop_server(m1, 1),
            stop_server(m2, 1),
            stop_server(m3, 1),
        )

        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        last_hash = b'\x00' * 32
        for i in range(10):
            block_dict = c.get_block(i)

            del block_dict['blockOwners']

            got = canonical.block_from_subblocks([s for s in fake_driver.blocks[i]['subBlocks']], previous_hash=last_hash,
                                                 block_num=i)

            last_hash = block_dict['blockHash']

            self.assertDictEqual(block_dict, got)
