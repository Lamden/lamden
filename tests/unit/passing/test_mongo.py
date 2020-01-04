from unittest import TestCase
from cilantro_ee.services.storage.master import MasterStorage
from cilantro_ee.crypto import wallet


class TestMasterDatabase(TestCase):
    def setUp(self):
        self.sk, self.vk = wallet.new()
        self.db = MasterStorage()

    def tearDown(self):
        self.db.drop_collections()

    def test_init_masterdatabase(self):
        self.assertIsNotNone(self.db.blocks)

    def test_insert_block_type_error_if_not_dict(self):
        with self.assertRaises(TypeError):
            self.db.put(123)

    def test_insert_block_returns_true_when_provided_correct_arguments(self):

        block = {
            'blockNum': 1,
            'sender': 'stu',
            'amount': 1000000
        }

        result = self.db.put(block)
        self.assertTrue(result)

    def test_get_block_number_returns_data(self):
        block = {
            'blockNum': 1,
            'sender': 'stu',
            'amount': 1000000
        }

        self.db.put(block)

        block = self.db.get_block(1)
        self.assertTrue(block)

    def test_drop_db(self):
        block = {
            'blockNum': 1,
            'sender': 'stu',
            'amount': 1000000
        }

        result = self.db.put(block)
        self.assertTrue(result)

        block = self.db.get_block(1)
        self.assertTrue(block)

        self.db.drop_collections()

        block = self.db.get_block(1)
        self.assertIsNone(block)

    def test_get_block_by_hash(self):
        block = {
            'blockNum': 1,
            'blockHash': 'a',
            'sender': 'stu',
            'amount': 1000000
        }

        result = self.db.put(block)
        self.assertTrue(result)

        stored_block = self.db.get_block('a')

        del block['_id']

        self.assertEqual(block, stored_block)

    def test_get_block_by_number(self):
        block = {
            'blockNum': 1,
            'blockHash': 'a',
            'sender': 'stu',
            'amount': 1000000
        }

        result = self.db.put(block)
        self.assertTrue(result)

        stored_block = self.db.get_block(1)

        del block['_id']

        self.assertEqual(block, stored_block)

    def test_fail_get_block_by_hash(self):
        block = {
            'blockNum': 1,
            'blockHash': 'a',
            'sender': 'stu',
            'amount': 1000000
        }

        result = self.db.put(block)
        self.assertTrue(result)

        stored_block = self.db.get_block('b')

        del block['_id']

        self.assertIsNone(stored_block)

    def test_fail_get_block_by_number(self):
        block = {
            'blockNum': 1,
            'blockHash': 'a',
            'sender': 'stu',
            'amount': 1000000
        }

        result = self.db.put(block)
        self.assertTrue(result)

        stored_block = self.db.get_block(2)

        del block['_id']

        self.assertIsNone(stored_block)

    def test_get_block_owners_block_number(self):
        block = {
            'blockNum': 1,
            'blockHash': 'a',
            'blockOwners': ['stu', 'raghu']
        }

        result = self.db.indexes.collection.insert_one(block)
        self.assertTrue(result)

        owners = self.db.get_owners(1)

        self.assertEqual(block['blockOwners'], owners)

    def test_get_block_owners_by_block_hash(self):
        block = {
            'blockNum': 1,
            'blockHash': 'a',
            'blockOwners': ['stu', 'raghu']
        }

        result = self.db.indexes.collection.insert_one(block)
        self.assertTrue(result)

        owners = self.db.get_owners('a')

        self.assertEqual(block['blockOwners'], owners)

    def test_get_block_owners_by_block_number_non_existent(self):
        block = {
            'blockNum': 1,
            'blockHash': 'a',
            'sender': 'stu',
            'amount': 1000000,
            'blockOwners': ['stu', 'raghu']
        }

        result = self.db.put(block)
        self.assertTrue(result)

        owners = self.db.get_owners(2)

        self.assertIsNone(owners)

    def test_get_block_owners_by_block_hash_non_existent(self):
        block = {
            'blockNum': 1,
            'blockHash': 'a',
            'sender': 'stu',
            'amount': 1000000,
            'blockOwners': ['stu', 'raghu']
        }

        result = self.db.put(block)
        self.assertTrue(result)

        owners = self.db.get_owners('x')

        self.assertIsNone(owners)

    def test_get_block_owners_bad_dict_returns_none(self):
        block = {
            'blockNum': 1,
            'blockHash': 'a',
            'sender': 'stu',
            'amount': 1000000,
            'blockOwners': ['stu', 'raghu']
        }

        result = self.db.put(block)
        self.assertTrue(result)

        owners = self.db.get_owners(1000)

        self.assertIsNone(owners)

    def test_create_genesis_block(self):
        block = self.db.get_block(0)

        self.assertIsNotNone(block)

    def test_query_last_n_blocks(self):
        block_1 = {
            'blockNum': 1,
            'blockHash': 'a',
            'blockOwners': ['stu', 'raghu']
        }

        block_2 = {
            'blockNum': 2,
            'blockHash': 'a',
            'blockOwners': ['stu', 'raghu']
        }

        block_3 = {
            'blockNum': 3,
            'blockHash': 'a',
            'blockOwners': ['stu', 'raghu']
        }

        block_4 = {
            'blockNum': 4,
            'blockHash': 'a',
            'blockOwners': ['stu', 'raghu']
        }

        block_5 = {
            'blockNum': 5,
            'blockHash': 'a',
            'blockOwners': ['stu', 'raghu']
        }

        self.db.indexes.collection.insert_one(block_1)
        self.db.indexes.collection.insert_one(block_2)
        self.db.indexes.collection.insert_one(block_3)
        self.db.indexes.collection.insert_one(block_4)
        self.db.indexes.collection.insert_one(block_5)

        blocks = self.db.get_last_n(3)

        nums = [block['blockNum'] for block in blocks]

        self.assertEqual(nums, [5, 4, 3])

    def test_query_too_many_blocks_returns_total(self):
        block_1 = {
            'blockNum': 1,
            'blockHash': 'a',
            'blockOwners': ['stu', 'raghu']
        }

        block_2 = {
            'blockNum': 2,
            'blockHash': 'a',
            'blockOwners': ['stu', 'raghu']
        }

        block_3 = {
            'blockNum': 3,
            'blockHash': 'a',
            'blockOwners': ['stu', 'raghu']
        }

        block_4 = {
            'blockNum': 4,
            'blockHash': 'a',
            'blockOwners': ['stu', 'raghu']
        }

        block_5 = {
            'blockNum': 5,
            'blockHash': 'a',
            'blockOwners': ['stu', 'raghu']
        }

        self.db.indexes.collection.insert_one(block_1)
        self.db.indexes.collection.insert_one(block_2)
        self.db.indexes.collection.insert_one(block_3)
        self.db.indexes.collection.insert_one(block_4)
        self.db.indexes.collection.insert_one(block_5)

        blocks = self.db.get_last_n(300)

        nums = [block['blockNum'] for block in blocks]

        self.assertEqual(nums, [5, 4, 3, 2, 1, 0])
