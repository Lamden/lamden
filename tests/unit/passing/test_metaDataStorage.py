from unittest import TestCase
from cilantro_ee.services.storage.state import MetaDataStorage
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
        bhash = b'a' * 6
        with self.assertRaises(AssertionError):
            self.db.set_latest_block_hash(bhash)

    def test_set_latest_block_hash_not_hex_fails(self):
        bhash = 'x' * 32
        with self.assertRaises(ValueError):
            self.db.set_latest_block_hash(bhash)

    def test_set_latest_block_hash_returns_when_successful(self):
        bhash = b'a' * 32

        self.db.set_latest_block_hash(bhash)

    def test_get_latest_block_hash_none(self):
        expected = b'\00' * 32

        got = self.db.get_latest_block_hash()

        self.assertEqual(expected, got)

    def test_get_latest_block_hash_after_setting(self):
        expected = b'a' * 32

        self.db.set_latest_block_hash(expected)

        got = self.db.get_latest_block_hash()

        self.assertEqual(expected, got)

    def test_latest_block_hash_as_property(self):
        expected = b'a' * 32

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
