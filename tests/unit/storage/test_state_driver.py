from unittest import TestCase
import unittest
from cilantro_ee.messages.transaction.data import TransactionDataBuilder
from cilantro_ee.messages.block_data.sub_block import SubBlockBuilder
from cilantro_ee.messages.block_data.block_data import GENESIS_BLOCK_HASH, BlockData
from cilantro_ee.storage.state import MetaDataStorage


class TestStateDriver(TestCase):
    def setUp(self):
        self.r = MetaDataStorage()  # this is a class, not an instance, so we do not instantiate
        self.r.flush()

    def test_state_updated(self):
        states = {
            'hello world': 'goodbye world',
            'entropy':'regression',
            'land': 'sea',
            'xxx': 'holic',
            'beyonce': 'sings',
            'cow': 'poo',
            'anthropologist': 'discovers;',
            'cranberry': 'juice',
            'optic': 'fiber',
            'before': 'after'
        }
        txs = []
        for i in range(len(states) // 2):
            txs.append(TransactionDataBuilder.create_random_tx(status='SUCC', state=states[i*2] + states[i*2+1]))

        sb = SubBlockBuilder.create(transactions=txs)
        block = BlockData.create(block_hash=BlockData.compute_block_hash([sb.merkle_root], GENESIS_BLOCK_HASH),
                                 prev_block_hash=GENESIS_BLOCK_HASH, block_owners=['AB'*32], block_num=1, sub_blocks=[sb])

        self.r.update_with_block(block)
        self.assertEqual(self.r.get('hello'), b'world')
        self.assertEqual(self.r.get('goodbye'), b'world')
        self.assertEqual(self.r.get('entropy'), b'regression')
        self.assertEqual(self.r.get('land'), b'sea')
        self.assertEqual(self.r.get('xxx'), b'holic')
        self.assertEqual(self.r.get('beyonce'), b'sings')
        self.assertEqual(self.r.get('cow'), b'poo')
        self.assertEqual(self.r.get('anthropologist'), b'discovers')
        self.assertEqual(self.r.get('cranberry'), b'juice')
        self.assertEqual(self.r.get('optic'), b'fiber')
        self.assertEqual(self.r.get('before'), b'after')

    # TODO test this with publish transactions

    def test_get_latest_block_hash_with_none_set(self):
        b_hash = self.r.get_latest_block_hash()
        self.assertEqual(GENESIS_BLOCK_HASH, b_hash)

    def test_get_latest_block_num_with_none_set(self):
        b_num = self.r.get_latest_block_num()
        self.assertEqual(0, b_num)

    def test_set_get_latest_block_hash(self):
        b_hash = 'ABCD' * 16
        self.r.set_latest_block_hash(b_hash)

        self.assertEqual(self.r.get_latest_block_hash(), b_hash)

    def test_set_get_latest_block_num(self):
        b_num = 9001
        self.r.set_latest_block_num(b_num)

        self.assertEqual(self.r.get_latest_block_num(), b_num)

if __name__ == '__main__':
    unittest.main()
