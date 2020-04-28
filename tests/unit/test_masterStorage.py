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

        self.assertEqual(q, {'hash': '1'})

    def test_genesis_block_created(self):
        block = self.db.get_block(0)

        expected = {
                'blockNum': 0,
                'hash': b'\x00' * 32,
                'blockOwners': [b'\x00' * 32]
            }

        self.assertEqual(block, expected)

        index = self.db.get_index(0)

        self.assertEqual(index, expected)

    def test_put_block(self):
        block = {
            'hash': 'a',
            'blockNum': 1,
            'data': 'woop'
        }

        _id = self.db.put(block)

        self.assertTrue(_id)

    def test_get_block(self):
        block = {
            'hash': 'a',
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
            'hash': 'a',
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
            'hash': 'a',
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
            'hash': 'a',
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
            'hash': 'a',
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
            'hash': 'a',
            'blockNum': 1,
            'blockOwners': 'stu'
        }

        _id = self.db.put(index, MasterStorage.INDEX)

        self.assertTrue(_id)

    def test_put_other(self):
        index = {
            'hash': 'a',
            'blockNum': 1,
            'blockOwners': 'stu'
        }

        _id = self.db.put(index, 999)

        self.assertFalse(_id)

    def test_get_owners_num(self):
        index = {
            'hash': 'a',
            'blockNum': 1,
            'blockOwners': 'stu'
        }

        _id = self.db.put(index, MasterStorage.INDEX)

        self.assertTrue(_id)

        owners = self.db.get_owners(1)

        self.assertEqual(owners, 'stu')

    def test_get_owners_hash(self):
        index = {
            'hash': 'a',
            'blockNum': 1,
            'blockOwners': 'stu'
        }

        _id = self.db.put(index, MasterStorage.INDEX)

        self.assertTrue(_id)

        owners = self.db.get_owners('a')

        self.assertEqual(owners, 'stu')

    def test_get_owners_doesnt_exist(self):
        index = {
            'hash': 'a',
            'blockNum': 1,
            'blockOwners': 'stu'
        }

        _id = self.db.put(index, MasterStorage.INDEX)

        self.assertTrue(_id)

        owners = self.db.get_owners('b')

        self.assertIsNone(owners)

    def test_get_last_n_blocks(self):
        blocks = []

        blocks.append({'hash': 'a', 'blockNum': 1, 'data': 'woop'})
        blocks.append({'hash': 'a', 'blockNum': 2, 'data': 'woop'})
        blocks.append({'hash': 'a', 'blockNum': 3, 'data': 'woop'})
        blocks.append({'hash': 'a', 'blockNum': 4, 'data': 'woop'})
        blocks.append({'hash': 'a', 'blockNum': 5, 'data': 'woop'})

        for block in blocks:
            self.db.put(block)

        got_blocks = self.db.get_last_n(3, MasterStorage.BLOCK)

        nums = [b['blockNum'] for b in got_blocks]

        self.assertEqual(nums, [5, 4, 3])

    def test_get_last_n_index(self):
        blocks = []

        blocks.append({'hash': 'a', 'blockNum': 1, 'data': 'woop'})
        blocks.append({'hash': 'a', 'blockNum': 2, 'data': 'woop'})
        blocks.append({'hash': 'a', 'blockNum': 3, 'data': 'woop'})
        blocks.append({'hash': 'a', 'blockNum': 4, 'data': 'woop'})
        blocks.append({'hash': 'a', 'blockNum': 5, 'data': 'woop'})

        for block in blocks:
            self.db.put(block, MasterStorage.INDEX)

        got_blocks = self.db.get_last_n(3, MasterStorage.INDEX)

        nums = [b['blockNum'] for b in got_blocks]

        self.assertEqual(nums, [5, 4, 3])

    def test_get_none_from_wrong_n_collection(self):
        blocks = []

        blocks.append({'hash': 'a', 'blockNum': 1, 'data': 'woop'})
        blocks.append({'hash': 'a', 'blockNum': 2, 'data': 'woop'})
        blocks.append({'hash': 'a', 'blockNum': 3, 'data': 'woop'})
        blocks.append({'hash': 'a', 'blockNum': 4, 'data': 'woop'})
        blocks.append({'hash': 'a', 'blockNum': 5, 'data': 'woop'})

        for block in blocks:
            self.db.put(block, MasterStorage.INDEX)

        got_blocks = self.db.get_last_n(3, 5)

        self.assertIsNone(got_blocks)
