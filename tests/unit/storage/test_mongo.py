from unittest import TestCase
from cilantro_ee.storage.mongo import MasterDatabase
from cilantro_ee.protocol import wallet


class TestMasterDatabase(TestCase):
    def setUp(self):
        self.sk, self.vk = wallet.new()

    def test_init_masterdatabase(self):
        m = MasterDatabase(signing_key=self.sk)
        self.assertIsNotNone(m.block_db)

    def test_insert_block_type_error_if_not_dict(self):
        m = MasterDatabase(signing_key=self.sk)

        with self.assertRaises(TypeError):
            m.insert_block(123)

    def test_insert_block_returns_true_when_provided_correct_arguments(self):
        m = MasterDatabase(signing_key=self.sk)

        block = {
            'blockNum': 0,
            'sender': 'stu',
            'amount': 1000000
        }

        result = m.insert_block(block)
        self.assertTrue(result)

    def test_insert_block_returns_false_if_none_provided(self):
        m = MasterDatabase(signing_key=self.sk)

        result = m.insert_block()
        self.assertFalse(result)

    def test_get_block_number_returns_data(self):
        m = MasterDatabase(signing_key=self.sk)

        block = {
            'blockNum': 0,
            'sender': 'stu',
            'amount': 1000000
        }

        m.insert_block(block)

        block = m.get_block({'blockNum': 0})
        self.assertTrue(block)

    def test_drop_db(self):
        m = MasterDatabase(signing_key=self.sk)

        block = {
            'blockNum': 0,
            'sender': 'stu',
            'amount': 1000000
        }

        result = m.insert_block(block)
        self.assertTrue(result)

        block = m.get_block({'blockNum': 0})
        self.assertTrue(block)

        m.drop_db()
        m.setup_db()

        block = m.get_block({'blockNum': 0})
        self.assertIsNone(block)
