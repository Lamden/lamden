from unittest import TestCase

from lamden.webserver.webserver import WebServer
from lamden.webserver.readers import AsyncBlockReader
from lamden.crypto.wallet import Wallet
from contracting.client import ContractingClient
from contracting.db.driver import ContractDriver, decode, encode
from lamden.storage import BlockStorage
from lamden.crypto.transaction import build_transaction
from lamden import storage

import asyncio

n = ContractDriver()


class TestAsyncBlockReader(TestCase):
    def setUp(self):
        self.w = Wallet()

        self.block_reader = AsyncBlockReader()
        self.loop = asyncio.get_event_loop()
        self.block_writer = BlockStorage()

    def tearDown(self):
        self.block_writer.flush()

    def test_q_num(self):
        q = self.block_reader.q(1)

        self.assertEqual(q, {'number': 1})

    def test_q_hash(self):
        q = self.block_reader.q('1')

        self.assertEqual(q, {'hash': '1'})

    def test_get_block(self):
        block = {
            'hash': 'a',
            'number': 1,
            'data': 'woop'
        }

        _id = self.block_writer.put(block)

        self.assertTrue(_id)

        got_block = self.loop.run_until_complete(self.block_reader.get_block(1))

        self.assertEqual(block, got_block)

    def test_get_block_hash(self):
        block = {
            'hash': 'a',
            'number': 1,
            'data': 'woop'
        }

        _id = self.block_writer.put(block)

        self.assertTrue(_id)

        got_block = self.loop.run_until_complete(self.block_reader.get_block('a'))

        self.assertEqual(block, got_block)

    def test_get_none_block(self):
        block = {
            'hash': 'a',
            'number': 1,
            'data': 'woop'
        }

        _id = self.block_writer.put(block)

        self.assertTrue(_id)

        got_block = self.loop.run_until_complete(self.block_reader.get_block('b'))

        self.assertIsNone(got_block)

    def test_got_none_block_num(self):
        block = {
            'hash': 'a',
            'number': 1,
            'data': 'woop'
        }

        _id = self.block_writer.put(block)

        self.assertTrue(_id)

        got_block = self.loop.run_until_complete(self.block_reader.get_block(2))

        self.assertIsNone(got_block)

    def test_drop_collections_block(self):
        block = {
            'hash': 'a',
            'number': 1,
            'data': 'woop'
        }

        _id = self.block_writer.put(block)

        self.assertTrue(_id)

        self.block_writer.drop_collections()

        got_block = self.loop.run_until_complete(self.block_reader.get_block(1))

        self.assertIsNone(got_block)

    def test_get_last_n_blocks(self):
        blocks = []

        blocks.append({'hash': 'a', 'number': 1, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 2, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 3, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 4, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 5, 'data': 'woop'})

        for block in blocks:
            self.block_writer.put(block)

        got_blocks = self.loop.run_until_complete(self.block_reader.get_last_n(3, BlockStorage.BLOCK))

        nums = [b['number'] for b in got_blocks]

        self.assertEqual(nums, [5, 4, 3])

    def test_get_last_n_index(self):
        blocks = []

        blocks.append({'hash': 'a', 'number': 1, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 2, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 3, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 4, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 5, 'data': 'woop'})

        for block in blocks:
            self.block_writer.put(block, BlockStorage.BLOCK)

        got_blocks = self.loop.run_until_complete(self.block_reader.get_last_n(3, BlockStorage.BLOCK))

        nums = [b['number'] for b in got_blocks]

        self.assertEqual(nums, [5, 4, 3])

    def test_get_none_from_wrong_n_collection(self):
        blocks = []

        blocks.append({'hash': 'a', 'number': 1, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 2, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 3, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 4, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 5, 'data': 'woop'})

        for block in blocks:
            self.block_writer.put(block, BlockStorage.BLOCK)

        got_blocks = self.loop.run_until_complete(self.block_reader.get_last_n(3, 5))

        self.assertIsNone(got_blocks)

    def test_store_and_get_tx(self):
        tx = {
            'hash': 'something',
            'key': 'value'
        }

        self.block_writer.put(tx, BlockStorage.TX)

        tx_got = self.loop.run_until_complete(self.block_reader.get_tx(h='something'))

        self.assertDictEqual(tx, tx_got)

    def test_get_non_existant_tx_returns_none(self):
        tx_got = self.loop.run_until_complete(self.block_reader.get_tx(h='something'))

        self.assertIsNone(tx_got)

    def test_store_txs_from_block_adds_all_txs(self):
        tx_1 = {
            'hash': 'something1',
            'key': '1'
        }

        tx_2 = {
            'hash': 'something2',
            'key': '2'
        }

        tx_3 = {
            'hash': 'something3',
            'key': '3'
        }

        block = {
            'subblocks': [
                {
                    'transactions': [tx_1, tx_2, tx_3]
                }
            ]
        }

        self.block_writer.store_txs(block)

        got_1 = self.loop.run_until_complete(self.block_reader.get_tx(h='something1'))
        got_2 = self.loop.run_until_complete(self.block_reader.get_tx(h='something2'))
        got_3 = self.loop.run_until_complete(self.block_reader.get_tx(h='something3'))

        self.assertDictEqual(tx_1, got_1)
        self.assertDictEqual(tx_2, got_2)
        self.assertDictEqual(tx_3, got_3)

    def test_store_block_stores_txs_and_block(self):
        tx_1 = {
            'hash': 'something1',
            'key': '1'
        }

        tx_2 = {
            'hash': 'something2',
            'key': '2'
        }

        tx_3 = {
            'hash': 'something3',
            'key': '3'
        }

        block = {
            'hash': 'hello',
            'subblocks': [
                {
                    'transactions': [tx_1, tx_2, tx_3]
                }
            ]
        }

        self.block_writer.store_block(block)

        got_1 = self.loop.run_until_complete(self.block_reader.get_tx(h='something1'))
        got_2 = self.loop.run_until_complete(self.block_reader.get_tx(h='something2'))
        got_3 = self.loop.run_until_complete(self.block_reader.get_tx(h='something3'))

        self.assertDictEqual(tx_1, got_1)
        self.assertDictEqual(tx_2, got_2)
        self.assertDictEqual(tx_3, got_3)

        got_block = self.loop.run_until_complete(self.block_reader.get_block('hello'))

        self.assertDictEqual(block, got_block)

    def test_get_block_v_none_returns_none(self):
        self.assertIsNone(self.loop.run_until_complete(self.block_reader.get_block()))

    def test_return_id_noid_false_block(self):
        block = {
            'hash': 'a',
            'number': 1,
            'data': 'woop'
        }

        self.block_writer.put(block)

        b = self.loop.run_until_complete(self.block_reader.get_block('a', no_id=False))

        self.assertIsNotNone(b.get('_id'))

        b = self.loop.run_until_complete(self.block_reader.get_block('a'))

        self.assertIsNone(b.get('_id'))

    def test_return_id_noid_false_tx(self):
        tx = {
            'hash': 'something',
            'key': 'value'
        }

        self.block_writer.put(tx, BlockStorage.TX)

        t = self.loop.run_until_complete(self.block_reader.get_tx(h='something', no_id=False))

        self.assertIsNotNone(t.get('_id'))

        t = self.loop.run_until_complete(self.block_reader.get_tx(h='something', no_id=True))

        self.assertIsNone(t.get('_id'))

