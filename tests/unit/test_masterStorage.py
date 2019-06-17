from unittest import TestCase
from cilantro_ee.storage.master import MasterStorage


class TestMasterStorage(TestCase):
    def setUp(self):
        self.db = MasterStorage()

    def tearDown(self):
        self.db.drop_collections()

    def test_init(self):
        self.assertTrue(self.db)

    def test_q_num(self):
        q = self.db.q(1)

        self.assertEqual(q, {'blockNum': 1})

    def test_q_hash(self):
        q = self.db.q('1')

        self.assertEqual(q, {'blockHash': '1'})

    def test_put_block(self):
        block = {
            'blockHash': 'a',
            'blockNum': 1,
            'data': 'woop'
        }

        _id = self.db.put(block)

        self.assertTrue(_id)

    def test_get_block(self):
        block = {
            'blockHash': 'a',
            'blockNum': 1,
            'data': 'woop'
        }

        _id = self.db.put(block)

        self.assertTrue(_id)

        got_block = self.db.get_block(1)

        block.pop('_id')

        self.assertEqual(block, got_block)

    def test_get_block_hash(self):
        block = {
            'blockHash': 'a',
            'blockNum': 1,
            'data': 'woop'
        }

        _id = self.db.put(block)

        self.assertTrue(_id)

        got_block = self.db.get_block('a')

        block.pop('_id')

        self.assertEqual(block, got_block)

    def test_get_none_block(self):
        block = {
            'blockHash': 'a',
            'blockNum': 1,
            'data': 'woop'
        }

        _id = self.db.put(block)

        self.assertTrue(_id)

        got_block = self.db.get_block('b')

        block.pop('_id')

        self.assertIsNone(got_block)

    def test_got_none_block_num(self):
        block = {
            'blockHash': 'a',
            'blockNum': 1,
            'data': 'woop'
        }

        _id = self.db.put(block)

        self.assertTrue(_id)

        got_block = self.db.get_block(2)

        block.pop('_id')

        self.assertIsNone(got_block)

    def test_drop_collections_block(self):
        block = {
            'blockHash': 'a',
            'blockNum': 1,
            'data': 'woop'
        }

        _id = self.db.put(block)

        self.assertTrue(_id)

        self.db.drop_collections()

        got_block = self.db.get_block(1)

        block.pop('_id')

        self.assertIsNone(got_block)

    def test_put_index(self):
        index = {
            'blockHash': 'a',
            'blockNum': 1,
            'blockOwners': 'stu'
        }

        _id = self.db.put(index, MasterStorage.INDEX)

        self.assertTrue(_id)

    def test_put_other(self):
        index = {
            'blockHash': 'a',
            'blockNum': 1,
            'blockOwners': 'stu'
        }

        _id = self.db.put(index, 999)

        self.assertFalse(_id)

    def test_get_owners_num(self):
        index = {
            'blockHash': 'a',
            'blockNum': 1,
            'blockOwners': 'stu'
        }

        _id = self.db.put(index, MasterStorage.INDEX)

        self.assertTrue(_id)

        owners = self.db.get_owners(1)

        self.assertEqual(owners, 'stu')

    def test_get_owners_hash(self):
        index = {
            'blockHash': 'a',
            'blockNum': 1,
            'blockOwners': 'stu'
        }

        _id = self.db.put(index, MasterStorage.INDEX)

        self.assertTrue(_id)

        owners = self.db.get_owners('a')

        self.assertEqual(owners, 'stu')

    def test_get_owners_doesnt_exist(self):
        index = {
            'blockHash': 'a',
            'blockNum': 1,
            'blockOwners': 'stu'
        }

        _id = self.db.put(index, MasterStorage.INDEX)

        self.assertTrue(_id)

        owners = self.db.get_owners('b')

        self.assertIsNone(owners)
