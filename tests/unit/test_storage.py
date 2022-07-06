from lamden import storage
from contracting.db.driver import ContractDriver, InMemDriver
from unittest import TestCase

from lamden.storage import BlockStorage
import json
import copy
import shutil
from pathlib import Path

from copy import deepcopy


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


class TestStorage(TestCase):
    def setUp(self):
        self.temp_storage_dir = Path.cwd().joinpath('temp_storage')
        try:
            shutil.rmtree(self.temp_storage_dir)
        except FileNotFoundError:
            pass

        self.temp_storage_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.block_storage = BlockStorage(root=Path.cwd().joinpath('temp_storage'))
        except Exception as err:
            print(err)

    def test_PRIVATE_METHOD_cull_transaction__return_tx_and_hash(self):
        block = {
            'hash': 'a',
            'number': 1,
            'processed': {
                'hash': 'XXX',
                'foo': 'bar'
            }
        }

        tx, hash = self.block_storage._BlockStorage__cull_tx(block)

        self.assertEqual({'hash': 'XXX', 'foo': 'bar'}, tx)
        self.assertEqual(hash, 'XXX')

    def test_PRIVATE_METHOD_cull_transaction__replaces_processed_with_hash(self):
        block = {
            'hash': 'a',
            'number': 1,
            'processed': {
                'hash': 'XXX',
                'foo': 'bar'
            }
        }

        self.block_storage._BlockStorage__cull_tx(block)

        self.assertEqual('XXX', block.get('processed'))


    def test_PRIVATE_METHOD_write_block__stores_block_by_num(self):
        block = {
            'hash': 'a',
            'number': 1,
            'hlc_timestamp': '1',
            'processed': {
                'hash': 'XXX',
                'foo': 'bar'
            }
        }

        self.block_storage._BlockStorage__write_block(block)

        filename = ('0' * 63) + '1'

        with open(self.block_storage.blocks_dir.joinpath(filename)) as f:
            b = json.load(f)

        self.assertEqual(block, b)

    def test_PRIVATE_METHOD_write_block__stores_hash_symlink(self):
        block = {
            'hash': 'a',
            'number': 1,
            'hlc_timestamp': '1',
            'processed': {
                'hash': 'XXX',
                'foo': 'bar'
            }
        }

        self.block_storage._BlockStorage__write_block(block)

        with open(self.block_storage.blocks_alias_dir.joinpath(block.get('hash'))) as f:
            b = json.load(f)

        self.assertEqual(block, b)

    def test_PRIVATE_METHOD_write_txs__stores_transactions_by_hash_and_payload(self):
        block = {
            'hash': 'a',
            'number': 1,
            'hlc_timestamp': '1',
            'processed': {
                'hash': 'XXX',
                'foo': 'bar'
            }
        }

        tx, tx_hash = self.block_storage._BlockStorage__cull_tx(block)

        self.block_storage._BlockStorage__write_tx(tx_hash=tx_hash, tx=tx)

        with open(self.block_storage.txs_dir.joinpath('XXX')) as f:
            t = json.load(f)

        self.assertEqual(tx, t)

    def test_METHOD_store_block__stores_block_and_aliases(self):
        block = {
            'hash': 'a',
            'number': 1,
            'hlc_timestamp': '1',
            'processed': {
                'hash': 'XXX',
                'foo': 'bar'
            }
        }

        self.block_storage.store_block(block)

        with open(self.block_storage.txs_dir.joinpath('XXX')) as f:
            t = json.load(f)

        _t = {
            'hash': 'XXX',
            'foo': 'bar'
        }

        self.assertEqual(t, _t)

        filename = ('0' * 63) + '1'
        with open(self.block_storage.blocks_dir.joinpath(filename)) as f:
            b = json.load(f)

        self.assertEqual(b, block)

        with open(self.block_storage.blocks_alias_dir.joinpath('a')) as f:
            bb = json.load(f)

        self.assertEqual(bb, block)

        with open(self.block_storage.blocks_alias_dir.joinpath('1')) as f:
            cc = json.load(f)

        self.assertEqual(cc, block)

    def test_METHOD_get_block__returns_block_by_block_number(self):
        block = {
            'hash': 'a',
            'number': 1,
            'hlc_timestamp': '1',
            'processed': {
                'hash': 'XXX'
            },
            'data': 'woop'
        }

        self.block_storage.store_block(deepcopy(block))

        got_block = self.block_storage.get_block(1)

        self.assertEqual(block, got_block)

    def test_METHOD_get_block__returns_block_by_block_hash(self):
        block = {
            'hash': 'a',
            'number': 1,
            'hlc_timestamp': '1',
            'processed': {
                'hash': 'XXX'
            },
            'data': 'woop'
        }

        self.block_storage.store_block(deepcopy(block))

        got_block = self.block_storage.get_block('a')

        self.assertEqual(block, got_block)

    def test_METHOD_get_block__returns_block_by_hlc_timestamp(self):
        block = {
            'hash': 'a',
            'number': 1,
            'hlc_timestamp': '2',
            'processed': {
                'hash': 'XXX'
            },
            'data': 'woop'
        }

        self.block_storage.store_block(deepcopy(block))

        got_block = self.block_storage.get_block('2')

        self.assertEqual(block, got_block)

    def test_METHOD_get_block__cannot_find_hash_returns_None_block(self):
        block = {
            'hash': 'a',
            'number': 1,
            'hlc_timestamp': '2',
            'processed': {
                'hash': 'XXX'
            },
            'data': 'woop'
        }

        self.block_storage.store_block(block)

        got_block = self.block_storage.get_block('b')

        self.assertIsNone(got_block)

    def test_METHOD_get_block__cannot_find_hlc_timestamp_returns_None_block(self):
        block = {
            'hash': 'a',
            'number': 1,
            'hlc_timestamp': '2',
            'processed': {
                'hash': 'XXX'
            },
            'data': 'woop'
        }

        self.block_storage.store_block(block)

        got_block = self.block_storage.get_block('3')

        self.assertIsNone(got_block)

    def test_METHOD_get_tx__cannot_find_tx_returns_None(self):
        tx_got = self.block_storage.get_tx('3')

        self.assertIsNone(tx_got)

    def test_METHOD_get_tx__returns_tx(self):
        block = {
            'hash': 'a',
            'number': 1,
            'hlc_timestamp': '2',
            'processed': {
                'hash': 'XXX'
            },
            'data': 'woop'
        }

        self.block_storage.store_block(block)

        tx_got = self.block_storage.get_tx('XXX')

        self.assertIsNotNone(tx_got)
        self.assertEqual('XXX', tx_got.get('hash'))


    def test_METHOD_store_block__stores_txs_and_block(self):
        block = {
            'hash': 'a',
            'number': 1,
            'hlc_timestamp': '1',
            'processed': {
                'hash': 'XXX',
                'foo': 'bar'
            }
        }

        self.block_storage.store_block(deepcopy(block))

        self.assertDictEqual(block.get('processed'), self.block_storage.get_tx(h='XXX'))

        self.assertDictEqual(block, self.block_storage.get_block(1))
        self.assertDictEqual(block, self.block_storage.get_block('a'))
        self.assertDictEqual(block, self.block_storage.get_block('1'))

    def test_get_block_v_none_returns_none(self):
        self.assertIsNone(self.block_storage.get_block())
