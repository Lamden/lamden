from unittest import TestCase
from cilantro_ee.storage.state import MetaDataStorage
from cilantro_ee.messages.transaction.data import TransactionDataBuilder, TransactionData
from cilantro_ee.messages.block_data.sub_block import SubBlock, SubBlockBuilder
from cilantro_ee.messages.block_data.block_data import GENESIS_BLOCK_HASH, BlockData
import json

class TestMetaDataStorage(TestCase):
    def setUp(self):
        self.db = MetaDataStorage()
        self.db.flush()

    def tearDown(self):
        self.db.flush()

    def test_init(self):
        self.assertIsNotNone(self.db)

    def test_set_latest_block_hash_not_64_chars(self):
        bhash = 'a' * 12
        with self.assertRaises(AssertionError):
            self.db.set_latest_block_hash(bhash)

    def test_set_latest_block_hash_not_hex_fails(self):
        bhash = 'x' * 64
        with self.assertRaises(ValueError):
            self.db.set_latest_block_hash(bhash)

    def test_set_latest_block_hash_returns_when_successful(self):
        bhash = 'a' * 64

        self.db.set_latest_block_hash(bhash)

    def test_get_latest_block_hash_none(self):
        expected = '0' * 64

        got = self.db.get_latest_block_hash()

        self.assertEqual(expected, got)

    def test_get_latest_block_hash_after_setting(self):
        expected = 'a' * 64

        self.db.set_latest_block_hash(expected)

        got = self.db.get_latest_block_hash()

        self.assertEqual(expected, got)

    def test_latest_block_hash_as_property(self):
        expected = 'a' * 64

        self.db.latest_block_hash = expected

        got = self.db.latest_block_hash

        self.assertEqual(expected, got)

    def test_set_latest_block_num_not_number(self):
        num = 'a'
        with self.assertRaises(ValueError):
            self.db.set_latest_block_num(num)

    def test_set_latest_block_num_negative_fails(self):
        num = -1000
        with self.assertRaises(AssertionError):
            self.db.set_latest_block_num(num)

    def test_set_latest_block_num_returns_when_successful(self):
        num = 64

        self.db.set_latest_block_num(num)

    def test_get_latest_block_num_none(self):
        got = self.db.get_latest_block_num()

        self.assertEqual(0, got)

    def test_get_latest_block_num_after_setting(self):
        num = 64

        self.db.set_latest_block_num(num)

        got = self.db.get_latest_block_num()

        self.assertEqual(num, got)

    def test_get_latest_block_num_as_property(self):
        num = 64

        self.db.latest_block_num = num

        got = self.db.latest_block_num

        self.assertEqual(num, got)

    def test_store_block_integration(self):
        states = [
            {'a': 1},
            {'b': 2},
            {'c': 3},
            {'d': 4},
            {'e': 5},
            {'f': 6},
            {'g': 7},
            {'h': 8},
            {'i': 9},
            {'j': 10},
        ]
        txs = []
        for i in range(len(states)):
            random_tx = TransactionDataBuilder.create_random_tx(status='SUCC',
                                                                state=json.dumps(states[i]))
            txs.append(random_tx)

        sb = SubBlockBuilder.create(transactions=txs)
        block = BlockData.create(block_hash=BlockData.compute_block_hash([sb.merkle_root], GENESIS_BLOCK_HASH),
                                 prev_block_hash=GENESIS_BLOCK_HASH, block_owners=['AB' * 32], block_num=1,
                                 sub_blocks=[sb])

        self.db.update_with_block(block)

        self.assertEqual(self.db.get('a'), b'1')
        self.assertEqual(self.db.get('b'), b'2')
        self.assertEqual(self.db.get('c'), b'3')
        self.assertEqual(self.db.get('d'), b'4')
        self.assertEqual(self.db.get('e'), b'5')
        self.assertEqual(self.db.get('f'), b'6')
        self.assertEqual(self.db.get('g'), b'7')
        self.assertEqual(self.db.get('h'), b'8')
        self.assertEqual(self.db.get('i'), b'9')
        self.assertEqual(self.db.get('j'), b'10')

        num = block.block_num
        h = block.block_hash

        self.assertEqual(self.db.latest_block_hash, h)
        self.assertEqual(self.db.latest_block_num, num)
