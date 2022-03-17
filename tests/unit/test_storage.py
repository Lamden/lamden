from lamden import storage
from contracting.db.driver import ContractDriver
from unittest import TestCase

from lamden.storage import BlockStorage
import json
import copy
from lamden.nodes.hlc import HLC_Clock


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
        v1 = self.driver.get('hello')
        v2 = self.driver.get('name')

        self.assertIsNone(v1)
        self.assertIsNone(v2)

        storage.update_state_with_transaction(
            tx=tx_1,
            driver=self.driver,
            nonces=self.nonces
        )

        v1 = self.driver.get('hello')
        v2 = self.driver.get('name')

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
        v1 = self.driver.get('hello')
        v2 = self.driver.get('name')

        v3 = self.driver.get('name2')

        v4 = self.driver.get('another')
        v5 = self.driver.get('something')

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

        v1 = self.driver.get('hello')
        v2 = self.driver.get('name')

        v3 = self.driver.get('name2')

        v4 = self.driver.get('another')
        v5 = self.driver.get('something')

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
        v1 = self.driver.get('hello')
        v2 = self.driver.get('name')

        v3 = self.driver.get('name2')

        v4 = self.driver.get('another')
        v5 = self.driver.get('something')

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

        v1 = self.driver.get('hello')
        v2 = self.driver.get('name')

        v3 = self.driver.get('name2')

        v4 = self.driver.get('another')
        v5 = self.driver.get('something')

        self.assertEqual(v1, 'there2')
        self.assertEqual(v2, 'jeff')
        self.assertEqual(v3, 'jeff2')
        self.assertEqual(v4, 'value')
        self.assertEqual(v5, 'else')


class TestStorage(TestCase):
    def setUp(self):
        self.db = storage.BlockStorage()

    def tearDown(self):
        self.db.flush()

    def test_cull_transaction_works_single_sb_and_tx(self):
        block = {
            'hash': 'a',
            'number': 1,
            'subblocks': [
                {
                    'transactions': [
                        {
                            'hash': 'XXX',
                            'foo': 'bar'
                        }
                    ]
                }
            ]
        }

        tx = {
                'hash': 'XXX',
                'foo': 'bar'
            }

        txs, hashes = self.db.cull_txs(block)
        expected_txs = [tx]
        expected_hashes = ['XXX']

        self.assertEqual(txs, expected_txs)
        self.assertEqual(hashes, expected_hashes)

    def test_cull_transaction_works_single_sb_multi_txs(self):
        block = {
            'hash': 'a',
            'number': 1,
            'subblocks': [
                {
                    'transactions': [
                        {
                            'hash': 'XXX',
                            'foo': 'bar'
                        },
                        {
                            'hash': 'XXY',
                            'foo': 'bar2'
                        },
                        {
                            'hash': 'XXF',
                            'foo2': 'bar'
                        }
                    ]
                }
            ]
        }

        expected_txs = [
            {
                'hash': 'XXX',
                'foo': 'bar'
            },
            {
                'hash': 'XXY',
                'foo': 'bar2'
            },
            {
                'hash': 'XXF',
                'foo2': 'bar'
            }
        ]

        expected_hashes = ['XXX', 'XXY', 'XXF']

        txs, hashes = self.db.cull_txs(block)

        self.assertEqual(txs, expected_txs)
        self.assertEqual(hashes, expected_hashes)

    def test_cull_transaction_works_multi_sb_multi_txs(self):
        block = {
            'hash': 'a',
            'number': 1,
            'subblocks': [
                {
                    'transactions': [
                        {
                            'hash': 'XXX',
                            'foo': 'bar'
                        },
                        {
                            'hash': 'XXY',
                            'foo': 'bar2'
                        },
                        {
                            'hash': 'XXF',
                            'foo2': 'bar'
                        }
                    ]
                },
                {
                    'transactions': [
                        {
                            'hash': 'YYY',
                            'foo3': 'bar3'
                        },
                        {
                            'hash': 'YYX',
                            'foo4': 'bar4'
                        },
                        {
                            'hash': 'YSX',
                            'foo5': 'bar5'
                        }
                    ]
                }
            ]
        }

        expected_txs = [
            {
                'hash': 'XXX',
                'foo': 'bar'
            },
            {
                'hash': 'XXY',
                'foo': 'bar2'
            },
            {
                'hash': 'XXF',
                'foo2': 'bar'
            },
            {
                'hash': 'YYY',
                'foo3': 'bar3'
            },
            {
                'hash': 'YYX',
                'foo4': 'bar4'
            },
            {
                'hash': 'YSX',
                'foo5': 'bar5'
            }
        ]

        expected_hashes = ['XXX', 'XXY', 'XXF', 'YYY', 'YYX', 'YSX']

        txs, hashes = self.db.cull_txs(block)

        self.assertEqual(txs, expected_txs)
        self.assertEqual(hashes, expected_hashes)

    def test_write_block_stores_block_by_num(self):
        block = {
            'hash': 'a',
            'number': 1,
            'subblocks': [
                {
                    'transactions': [
                        {
                            'hash': 'XXX',
                            'foo': 'bar'
                        }
                    ]
                }
            ]
        }

        self.db.write_block(block)

        filename = ('0' * 63) + '1'

        with open(self.db.blocks_dir.joinpath(filename)) as f:
            b = json.load(f)

        self.assertEqual(block, b)

    def test_write_block_stores_symlink_by_hash(self):
        block = {
            'hash': 'a',
            'number': 1,
            'subblocks': [
                {
                    'transactions': [
                        {
                            'hash': 'XXX',
                            'foo': 'bar'
                        }
                    ]
                }
            ]
        }

        self.db.write_block(block)

        with open(self.db.blocks_alias_dir.joinpath(block.get('hash'))) as f:
            b = json.load(f)

        self.assertEqual(block, b)

    def test_write_txs_stores_transactions_by_hash_and_payload(self):
        block = {
            'hash': 'a',
            'number': 1,
            'subblocks': [
                {
                    'transactions': [
                        {
                            'hash': 'XXX',
                            'foo': 'bar'
                        }
                    ]
                }
            ]
        }

        txs, hashes = self.db.cull_txs(block)

        self.db.write_txs(txs, hashes)

        with open(self.db.txs_dir.joinpath('XXX')) as f:
            t = json.load(f)

        self.assertEqual(txs[0], t)

    def test_store_block_completes_loop(self):
        block = {
            'hash': 'a',
            'number': 1,
            'subblocks': [
                {
                    'transactions': [
                        {
                            'hash': 'XXX',
                            'foo': 'bar'
                        },

                    ]
                },
            ]
        }

        self.db.store_block(block)

        with open(self.db.txs_dir.joinpath('XXX')) as f:
            t = json.load(f)

        _t = {
            'hash': 'XXX',
            'foo': 'bar'
        }

        self.assertEqual(t, _t)

        filename = ('0' * 63) + '1'
        with open(self.db.blocks_dir.joinpath(filename)) as f:
            b = json.load(f)

        self.assertEqual(b, block)

        with open(self.db.blocks_alias_dir.joinpath('a')) as f:
            bb = json.load(f)

        self.assertEqual(bb, block)

    def test_get_block(self):
        block = {
            'hash': 'a',
            'number': 1,
            'data': 'woop',
            'subblocks':[]
        }

        self.db.store_block(block)

        got_block = self.db.get_block(1)

        self.assertEqual(block, got_block)

    def test_get_block_hash(self):
        block = {
            'hash': 'a',
            'number': 1,
            'data': 'woop',
            'subblocks': []
        }

        self.db.store_block(block)

        got_block = self.db.get_block('a')

        self.assertEqual(block, got_block)

    def test_get_none_block(self):
        block = {
            'hash': 'a',
            'number': 1,
            'data': 'woop'
        }

        self.db.store_block(block)

        got_block = self.db.get_block('b')

        self.assertIsNone(got_block)

    def test_got_none_block_num(self):
        block = {
            'hash': 'a',
            'number': 1,
            'data': 'woop',
            'subblocks': []
        }

        self.db.store_block(block)

        got_block = self.db.get_block(2)

        self.assertIsNone(got_block)

    def test_get_non_existant_tx_returns_none(self):
        tx_got = self.db.get_tx(h='something')

        self.assertIsNone(tx_got)

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
            'number': 1,
            'subblocks': [
                {
                    'transactions': [tx_1, tx_2, tx_3]
                }
            ]
        }

        expected = copy.deepcopy(block)

        self.db.store_block(block)

        got_1 = self.db.get_tx(h='something1')
        got_2 = self.db.get_tx(h='something2')
        got_3 = self.db.get_tx(h='something3')

        self.assertDictEqual(tx_1, got_1)
        self.assertDictEqual(tx_2, got_2)
        self.assertDictEqual(tx_3, got_3)

        got_block = self.db.get_block('hello')

        self.assertDictEqual(expected, got_block)

    def test_get_block_v_none_returns_none(self):
        self.assertIsNone(self.db.get_block())


class TestMetaDataDriver(TestCase):
    def setUp(self):
        self.metadata = storage.MetaDataDriver()

    def tearDown(self):
        self.metadata.flush()

    def test_set_get_hlc_is_equal_to_python_objects(self):
        clock = HLC_Clock()

        time = clock.get_new_hlc_timestamp()

        self.metadata.set_last_processed_hlc(time)

        _time = self.metadata.get_last_processed_hlc()

        self.assertEqual(time, _time)