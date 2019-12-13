from unittest import TestCase
from cilantro_ee.core.top import TopBlockManager, BLOCK_HASH_KEY, BLOCK_NUMBER_KEY


class TestTopBlockManager(TestCase):
    def setUp(self):
        self.t = TopBlockManager()

    def tearDown(self):
        self.t.driver.flush()
        self.t.driver.reset_cache()

    def test_get_latest_block_hash_none(self):
        self.assertEqual(self.t.get_latest_block_hash(), b'\x00' * 32)

    def test_get_latest_block_hash_already_exists(self):
        self.t.driver.set(BLOCK_HASH_KEY, b'\xAA' * 32)
        self.assertEqual(self.t.get_latest_block_hash(), b'\xAA' * 32)

    def test_set_latest_block_hash(self):
        self.t.set_latest_block_hash(b'\xBB' * 32)
        self.assertEqual(self.t.get_latest_block_hash(), b'\xBB' * 32)

    def test_get_latest_block_num_none(self):
        self.assertEqual(self.t.get_latest_block_number(), 0)

    def test_get_latest_block_hash_already_exists(self):
        self.t.driver.set(BLOCK_NUMBER_KEY, 123)
        self.assertEqual(self.t.get_latest_block_number(), 123)

    def test_set_latest_block_hash(self):
        self.t.set_latest_block_number(32)
        self.assertEqual(self.t.get_latest_block_number(), 32)
