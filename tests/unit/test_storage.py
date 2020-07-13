from cilantro import storage
from contracting.db.driver import ContractDriver
from unittest import TestCase

from cilantro.storage import BlockStorage


class TestNonce(TestCase):
    def setUp(self):
        self.nonces = storage.NonceStorage()
        self.nonces.flush()

    def tearDown(self):
        self.nonces.flush()

    def test_get_nonce_none_if_not_set_first(self):
        n = self.nonces.get_nonce(
            sender='test',
            processor='test2'
        )

        self.assertIsNone(n)

    def test_get_pending_nonce_none_if_not_set_first(self):
        n = self.nonces.get_pending_nonce(
            sender='test',
            processor='test2'
        )

        self.assertIsNone(n)

    def test_set_then_get_nonce_returns_set_nonce(self):
        self.nonces.set_nonce(
            sender='test',
            processor='test2',
            value=2
        )

        n = self.nonces.get_nonce(
            sender='test',
            processor='test2'
        )

        self.assertEqual(n, 2)

    def test_set_then_get_pending_nonce_returns_set_pending_nonce(self):
        self.nonces.set_pending_nonce(
            sender='test',
            processor='test2',
            value=2
        )

        n = self.nonces.get_pending_nonce(
            sender='test',
            processor='test2'
        )

        self.assertEqual(n, 2)

    def test_get_latest_nonce_zero_if_none_set(self):
        n = self.nonces.get_latest_nonce(
            sender='test',
            processor='test2'
        )

        self.assertEqual(n, 0)

    def test_get_latest_nonce_returns_pending_nonce_if_not_none(self):
        self.nonces.set_pending_nonce(
            sender='test',
            processor='test2',
            value=2
        )

        n = self.nonces.get_latest_nonce(
            sender='test',
            processor='test2'
        )

        self.assertEqual(n, 2)

    def test_get_latest_nonce_nonce_if_pending_nonce_is_none(self):
        self.nonces.set_nonce(
            sender='test',
            processor='test2',
            value=2
        )

        n = self.nonces.get_latest_nonce(
            sender='test',
            processor='test2'
        )

        self.assertEqual(n, 2)


class TestStorage(TestCase):
    def setUp(self):
        self.driver = ContractDriver()
        self.driver.flush()

    def tearDown(self):
        self.driver.flush()

    def test_get_latest_block_hash_0s_if_none(self):
        h = storage.get_latest_block_hash(self.driver)
        self.assertEqual(h, '0' * 64)

    def test_get_latest_block_hash_correct_after_set(self):
        storage.set_latest_block_hash('a' * 64, self.driver)
        h = storage.get_latest_block_hash(self.driver)
        self.assertEqual(h, 'a' * 64)

    def test_get_latest_block_height_0_if_none(self):
        h = storage.get_latest_block_height(self.driver)
        self.assertEqual(h, 0)

    def test_get_latest_block_height_correct_after_set(self):
        storage.set_latest_block_height(123, self.driver)
        h = storage.get_latest_block_height(self.driver)
        self.assertEqual(h, 123)


tx_1 = {
    'transaction': {
        'payload': {
            'sender': 'abc',
            'processor': 'def',
            'nonce': 123,
        }
    },
    'state': [
        {
            'key': 'hello', 'value': 'there'
        },
        {
            'key': 'name', 'value': 'jeff'
        }
    ]
}

tx_2 = {
    'transaction': {
        'payload': {
            'sender': 'abc',
            'processor': 'def',
            'nonce': 124,
        }
    },
    'state': [
        {
            'key': 'hello', 'value': 'there2'
        },
        {
            'key': 'name2', 'value': 'jeff2'
        }
    ]
}

tx_3 = {
    'transaction': {
        'payload': {
            'sender': 'xxx',
            'processor': 'yyy',
            'nonce': 42,
        }
    },
    'state': [
        {
            'key': 'another', 'value': 'value'
        },
        {
            'key': 'something', 'value': 'else'
        }
    ]
}


block = {
    'hash': 'f' * 64,
    'number': 555,
    'subblocks': [
        {
            'transactions': [tx_1, tx_2]
        },
        {
            'transactions': [tx_3]
        }
    ]
}


class TestUpdatingState(TestCase):
    def setUp(self):
        self.driver = ContractDriver()
        self.nonces = storage.NonceStorage()
        self.nonces.flush()
        self.driver.flush()
        self.driver.clear_pending_state()

    def tearDown(self):
        self.nonces.flush()
        self.driver.flush()
        self.driver.clear_pending_state()

    def test_state_updated_to_correct_values_in_tx(self):
        v1 = self.driver.get('hello', mark=False)
        v2 = self.driver.get('name', mark=False)

        self.assertIsNone(v1)
        self.assertIsNone(v2)

        storage.update_state_with_transaction(
            tx=tx_1,
            driver=self.driver,
            nonces=self.nonces
        )

        v1 = self.driver.get('hello', mark=False)
        v2 = self.driver.get('name', mark=False)

        self.assertEqual(v1, 'there')
        self.assertEqual(v2, 'jeff')

    def test_nonces_set_to_tx_value(self):
        n = self.nonces.get_latest_nonce(sender='abc', processor='def')
        self.assertEqual(n, 0)

        storage.update_state_with_transaction(
            tx=tx_1,
            driver=self.driver,
            nonces=self.nonces
        )

        n = self.nonces.get_latest_nonce(sender='abc', processor='def')
        self.assertEqual(n, 124)

    def test_nonces_deleted_after_all_updates(self):
        self.nonces.set_pending_nonce(
            sender='abc',
            processor='def',
            value=122
        )

        n = self.nonces.get_pending_nonce(sender='abc', processor='def')

        self.assertEqual(n, 122)

        storage.update_state_with_transaction(
            tx=tx_1,
            driver=self.driver,
            nonces=self.nonces
        )

        n = self.nonces.get_pending_nonce(sender='abc', processor='def')

        self.assertEqual(n, None)

    def test_multiple_txs_deletes_multiple_nonces(self):
        self.nonces.set_pending_nonce(
            sender='abc',
            processor='def',
            value=122
        )

        n = self.nonces.get_pending_nonce(sender='abc', processor='def')
        self.assertEqual(n, 122)

        self.nonces.set_pending_nonce(
            sender='xxx',
            processor='yyy',
            value=4
        )

        n = self.nonces.get_pending_nonce(sender='xxx', processor='yyy')
        self.assertEqual(n, 4)

        storage.update_state_with_transaction(
            tx=tx_1,
            driver=self.driver,
            nonces=self.nonces
        )

        storage.update_state_with_transaction(
            tx=tx_2,
            driver=self.driver,
            nonces=self.nonces
        )

        storage.update_state_with_transaction(
            tx=tx_3,
            driver=self.driver,
            nonces=self.nonces
        )

        n = self.nonces.get_pending_nonce(sender='abc', processor='def')
        self.assertEqual(n, None)

        n = self.nonces.get_pending_nonce(sender='xxx', processor='yyy')
        self.assertEqual(n, None)

        n = self.nonces.get_latest_nonce(sender='abc', processor='def')
        self.assertEqual(n, 125)

        n = self.nonces.get_latest_nonce(sender='xxx', processor='yyy')
        self.assertEqual(n, 43)

    def test_multiple_tx_state_updates_correctly(self):
        v1 = self.driver.get('hello', mark=False)
        v2 = self.driver.get('name', mark=False)

        v3 = self.driver.get('name2', mark=False)

        v4 = self.driver.get('another', mark=False)
        v5 = self.driver.get('something', mark=False)

        self.assertIsNone(v1)
        self.assertIsNone(v2)
        self.assertIsNone(v3)
        self.assertIsNone(v4)
        self.assertIsNone(v5)

        storage.update_state_with_transaction(
            tx=tx_1,
            driver=self.driver,
            nonces=self.nonces
        )

        storage.update_state_with_transaction(
            tx=tx_2,
            driver=self.driver,
            nonces=self.nonces
        )

        storage.update_state_with_transaction(
            tx=tx_3,
            driver=self.driver,
            nonces=self.nonces
        )

        v1 = self.driver.get('hello', mark=False)
        v2 = self.driver.get('name', mark=False)

        v3 = self.driver.get('name2', mark=False)

        v4 = self.driver.get('another', mark=False)
        v5 = self.driver.get('something', mark=False)

        self.assertEqual(v1, 'there2')
        self.assertEqual(v2, 'jeff')
        self.assertEqual(v3, 'jeff2')
        self.assertEqual(v4, 'value')
        self.assertEqual(v5, 'else')

    def test_update_with_block_sets_hash_and_height(self):
        _hash = storage.get_latest_block_hash(self.driver)
        num = storage.get_latest_block_height(self.driver)

        self.assertEqual(_hash, '0' * 64)
        self.assertEqual(num, 0)

        storage.update_state_with_block(
            block=block,
            driver=self.driver,
            nonces=self.nonces
        )

        _hash = storage.get_latest_block_hash(self.driver)
        num = storage.get_latest_block_height(self.driver)

        self.assertEqual(_hash, 'f' * 64)
        self.assertEqual(num, 555)

    def test_update_with_block_sets_nonces_correctly(self):
        self.nonces.set_pending_nonce(
            sender='abc',
            processor='def',
            value=122
        )

        n = self.nonces.get_pending_nonce(sender='abc', processor='def')
        self.assertEqual(n, 122)

        self.nonces.set_pending_nonce(
            sender='xxx',
            processor='yyy',
            value=4
        )

        n = self.nonces.get_pending_nonce(sender='xxx', processor='yyy')
        self.assertEqual(n, 4)

        storage.update_state_with_block(
            block=block,
            driver=self.driver,
            nonces=self.nonces
        )

        n = self.nonces.get_pending_nonce(sender='abc', processor='def')
        self.assertEqual(n, None)

        n = self.nonces.get_pending_nonce(sender='xxx', processor='yyy')
        self.assertEqual(n, None)

        n = self.nonces.get_latest_nonce(sender='abc', processor='def')
        self.assertEqual(n, 125)

        n = self.nonces.get_latest_nonce(sender='xxx', processor='yyy')
        self.assertEqual(n, 43)

    def test_update_state_with_block_sets_state_correctly(self):
        v1 = self.driver.get('hello', mark=False)
        v2 = self.driver.get('name', mark=False)

        v3 = self.driver.get('name2', mark=False)

        v4 = self.driver.get('another', mark=False)
        v5 = self.driver.get('something', mark=False)

        self.assertIsNone(v1)
        self.assertIsNone(v2)
        self.assertIsNone(v3)
        self.assertIsNone(v4)
        self.assertIsNone(v5)

        storage.update_state_with_block(
            block=block,
            driver=self.driver,
            nonces=self.nonces
        )

        v1 = self.driver.get('hello', mark=False)
        v2 = self.driver.get('name', mark=False)

        v3 = self.driver.get('name2', mark=False)

        v4 = self.driver.get('another', mark=False)
        v5 = self.driver.get('something', mark=False)

        self.assertEqual(v1, 'there2')
        self.assertEqual(v2, 'jeff')
        self.assertEqual(v3, 'jeff2')
        self.assertEqual(v4, 'value')
        self.assertEqual(v5, 'else')


class TestMasterStorage(TestCase):
    def setUp(self):
        self.db = BlockStorage()

    def tearDown(self):
        self.db.drop_collections()

    def test_init(self):
        self.assertTrue(self.db)

    def test_q_num(self):
        q = self.db.q(1)

        self.assertEqual(q, {'number': 1})

    def test_q_hash(self):
        q = self.db.q('1')

        self.assertEqual(q, {'hash': '1'})

    def test_put_block(self):
        block = {
            'hash': 'a',
            'number': 1,
            'data': 'woop'
        }

        _id = self.db.put(block)

        self.assertTrue(_id)

    def test_get_block(self):
        block = {
            'hash': 'a',
            'number': 1,
            'data': 'woop'
        }

        _id = self.db.put(block)

        self.assertTrue(_id)

        got_block = self.db.get_block(1)

        self.assertEqual(block, got_block)

    def test_get_block_hash(self):
        block = {
            'hash': 'a',
            'number': 1,
            'data': 'woop'
        }

        _id = self.db.put(block)

        self.assertTrue(_id)

        got_block = self.db.get_block('a')

        self.assertEqual(block, got_block)

    def test_get_none_block(self):
        block = {
            'hash': 'a',
            'number': 1,
            'data': 'woop'
        }

        _id = self.db.put(block)

        self.assertTrue(_id)

        got_block = self.db.get_block('b')

        self.assertIsNone(got_block)

    def test_got_none_block_num(self):
        block = {
            'hash': 'a',
            'number': 1,
            'data': 'woop'
        }

        _id = self.db.put(block)

        self.assertTrue(_id)

        got_block = self.db.get_block(2)

        self.assertIsNone(got_block)

    def test_drop_collections_block(self):
        block = {
            'hash': 'a',
            'number': 1,
            'data': 'woop'
        }

        _id = self.db.put(block)

        self.assertTrue(_id)

        self.db.drop_collections()

        got_block = self.db.get_block(1)

        self.assertIsNone(got_block)

    def test_put_other(self):
        index = {
            'hash': 'a',
            'number': 1,
            'blockOwners': 'stu'
        }

        _id = self.db.put(index, 999)

        self.assertFalse(_id)

    def test_get_last_n_blocks(self):
        blocks = []

        blocks.append({'hash': 'a', 'number': 1, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 2, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 3, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 4, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 5, 'data': 'woop'})

        for block in blocks:
            self.db.put(block)

        got_blocks = self.db.get_last_n(3, BlockStorage.BLOCK)

        nums = [b['number'] for b in got_blocks]

        self.assertEqual(nums, [5, 4, 3])

    def test_get_last_n_index(self):
        blocks = []

        blocks.append({'hash': 'a', 'number': 1, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 2, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 3, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 4, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 5, 'data': 'woop'})

        for block in blocks:
            self.db.put(block, BlockStorage.BLOCK)

        got_blocks = self.db.get_last_n(3, BlockStorage.BLOCK)

        nums = [b['number'] for b in got_blocks]

        self.assertEqual(nums, [5, 4, 3])

    def test_get_none_from_wrong_n_collection(self):
        blocks = []

        blocks.append({'hash': 'a', 'number': 1, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 2, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 3, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 4, 'data': 'woop'})
        blocks.append({'hash': 'a', 'number': 5, 'data': 'woop'})

        for block in blocks:
            self.db.put(block, BlockStorage.BLOCK)

        got_blocks = self.db.get_last_n(3, 5)

        self.assertIsNone(got_blocks)

    def test_store_and_get_tx(self):
        tx = {
            'hash': 'something',
            'key': 'value'
        }

        self.db.put(tx, BlockStorage.TX)

        tx_got = self.db.get_tx(h='something')

        self.assertDictEqual(tx, tx_got)

    def test_get_non_existant_tx_returns_none(self):
        tx_got = self.db.get_tx(h='something')

        self.assertIsNone(tx_got)

    def test_store_txs_from_block_adds_all_txs(self):
        tx_1 = {
            'hash': 'something1',
            'key': '1'
        }

        tx_2 = {
            'hash': 'something2',
            'key': '2'
        }

        tx_3 = {
            'hash': 'something3',
            'key': '3'
        }

        block = {
            'subblocks': [
                {
                    'transactions': [tx_1, tx_2, tx_3]
                }
            ]
        }

        self.db.store_txs(block)

        got_1 = self.db.get_tx(h='something1')
        got_2 = self.db.get_tx(h='something2')
        got_3 = self.db.get_tx(h='something3')

        self.assertDictEqual(tx_1, got_1)
        self.assertDictEqual(tx_2, got_2)
        self.assertDictEqual(tx_3, got_3)

    def test_store_block_stores_txs_and_block(self):
        tx_1 = {
            'hash': 'something1',
            'key': '1'
        }

        tx_2 = {
            'hash': 'something2',
            'key': '2'
        }

        tx_3 = {
            'hash': 'something3',
            'key': '3'
        }

        block = {
            'hash': 'hello',
            'subblocks': [
                {
                    'transactions': [tx_1, tx_2, tx_3]
                }
            ]
        }

        self.db.store_block(block)

        got_1 = self.db.get_tx(h='something1')
        got_2 = self.db.get_tx(h='something2')
        got_3 = self.db.get_tx(h='something3')

        self.assertDictEqual(tx_1, got_1)
        self.assertDictEqual(tx_2, got_2)
        self.assertDictEqual(tx_3, got_3)

        got_block = self.db.get_block('hello')

        self.assertDictEqual(block, got_block)

    def test_get_block_v_none_returns_none(self):
        self.assertIsNone(self.db.get_block())
