from unittest import TestCase
from cilantro_ee.storage.mongo import MasterDatabase
from cilantro_ee.protocol import wallet


class TestMasterDatabase(TestCase):
    def setUp(self):
        self.sk, self.vk = wallet.new()
        self.db = MasterDatabase(signing_key=self.sk)

    def tearDown(self):
        self.db.drop_db()

    def test_init_masterdatabase(self):
        self.assertIsNotNone(self.db.block_db)

    def test_insert_block_type_error_if_not_dict(self):
        with self.assertRaises(TypeError):
            self.db.insert_block(123)

    def test_insert_block_returns_true_when_provided_correct_arguments(self):

        block = {
            'blockNum': 0,
            'sender': 'stu',
            'amount': 1000000
        }

        result = self.db.insert_block(block)
        self.assertTrue(result)

    def test_insert_block_returns_false_if_none_provided(self):
        result = self.db.insert_block()
        self.assertFalse(result)

    def test_get_block_number_returns_data(self):
        block = {
            'blockNum': 0,
            'sender': 'stu',
            'amount': 1000000
        }

        self.db.insert_block(block)

        block = self.db.get_block_by_number(0)
        self.assertTrue(block)

    def test_drop_db(self):
        block = {
            'blockNum': 0,
            'sender': 'stu',
            'amount': 1000000
        }

        result = self.db.insert_block(block)
        self.assertTrue(result)

        block = self.db.get_block_by_number(0)
        self.assertTrue(block)

        self.db.drop_db()

        block = self.db.get_block_by_number(0)
        self.assertIsNone(block)

    def test_get_block_by_hash(self):
        block = {
            'blockNum': 0,
            'blockHash': 'a',
            'sender': 'stu',
            'amount': 1000000
        }

        result = self.db.insert_block(block)
        self.assertTrue(result)

        stored_block = self.db.get_block_by_hash('a')

        self.assertEqual(block, stored_block)

    def test_get_block_by_number(self):
        block = {
            'blockNum': 0,
            'blockHash': 'a',
            'sender': 'stu',
            'amount': 1000000
        }

        result = self.db.insert_block(block)
        self.assertTrue(result)

        stored_block = self.db.get_block_by_number(0)

        self.assertEqual(block, stored_block)

    def test_fail_get_block_by_hash(self):
        block = {
            'blockNum': 0,
            'blockHash': 'a',
            'sender': 'stu',
            'amount': 1000000
        }

        result = self.db.insert_block(block)
        self.assertTrue(result)

        stored_block = self.db.get_block_by_hash('b')

        self.assertIsNone(stored_block)

    def test_fail_get_block_by_number(self):
        block = {
            'blockNum': 0,
            'blockHash': 'a',
            'sender': 'stu',
            'amount': 1000000
        }

        result = self.db.insert_block(block)
        self.assertTrue(result)

        stored_block = self.db.get_block_by_number(1)

        self.assertIsNone(stored_block)

