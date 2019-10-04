from unittest import TestCase
from cilantro_ee.core.epochs import EpochManager, EPOCH_HASH_KEY, EPOCH_NUMBER_KEY
from tests import random_txs


class TestEpochManager(TestCase):
    def setUp(self):
        self.e = EpochManager()

    def tearDown(self):
        self.e.driver.flush()
        self.e.driver.reset_cache()

    def test_get_epoch_hash(self):
        self.assertEqual(self.e.get_epoch_hash(), b'x/00' * 32)

    def test_get_epoch_hash_already_exists(self):
        self.e.driver.set(EPOCH_HASH_KEY, b'x/AA' * 32)
        self.assertEqual(self.e.get_epoch_hash(), b'x/AA' * 32)

    def test_set_epoch_hash(self):
        self.e.set_epoch_hash(b'x/BB' * 32)
        self.assertEqual(self.e.get_epoch_hash(), b'x/BB' * 32)

    def test_get_epoch_number_none(self):
        self.assertEqual(self.e.get_epoch_number(), 0)

    def test_get_epoch_number_already_exists(self):
        self.e.driver.set(EPOCH_NUMBER_KEY, 123)
        self.assertEqual(self.e.get_epoch_number(), 123)

    def test_set_epoch_number(self):
        self.e.set_epoch_number(32)
        self.assertEqual(self.e.get_epoch_number(), 32)

    def test_epoch_updates_if_needed(self):
        block = random_txs.random_block(block_num=4000)
        h = block.blockHash
        self.e.update_epoch_if_needed(block)
        self.assertEqual(self.e.get_epoch_hash(), h)
        self.assertEqual(self.e.get_epoch_number(), 40)

    def test_epoch_doesnt_update_if_not_needed(self):
        self.e.set_epoch_hash(b'x/AA' * 32)
        self.e.set_epoch_number(12)

        block = random_txs.random_block(block_num=1234)
        h = block.blockHash

        self.e.update_epoch_if_needed(block)
        self.assertEqual(self.e.get_epoch_hash(), b'x/AA' * 32)
        self.assertEqual(self.e.get_epoch_number(), 12)
