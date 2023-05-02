import os.path

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
        self.nonces = storage.NonceStorage(root='/tmp')
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
        if self.temp_storage_dir.is_dir():
            shutil.rmtree(self.temp_storage_dir)

        self.block_storage = BlockStorage(root=self.temp_storage_dir)

    def tearDown(self):
        pass

    def test_PRIVATE_METHOD_cull_transaction__return_tx_and_hash(self):
        block = {
            'hash': '78238403271a8dcd3c1031b144ace7dfdbe760108f2953b85d40c763fc79e4d4',
            'number': '1658163894967101696',
            'processed': {
                'hash': '5a5bbc6c0388b5f76d9da11b39ed4df8c47b9d4c231c72bb09b1b5e689699e77',
                'foo': 'bar'
            }
        }

        tx, hash = self.block_storage._BlockStorage__cull_tx(block)

        self.assertEqual({'hash': '5a5bbc6c0388b5f76d9da11b39ed4df8c47b9d4c231c72bb09b1b5e689699e77', 'foo': 'bar'}, tx)
        self.assertEqual(hash, '5a5bbc6c0388b5f76d9da11b39ed4df8c47b9d4c231c72bb09b1b5e689699e77')

    def test_PRIVATE_METHOD_cull_transaction__replaces_processed_with_hash(self):
        block = {
            'hash': '78238403271a8dcd3c1031b144ace7dfdbe760108f2953b85d40c763fc79e4d4',
            'number': '1658163894967101696',
            'processed': {
                'hash': '5a5bbc6c0388b5f76d9da11b39ed4df8c47b9d4c231c72bb09b1b5e689699e77',
                'foo': 'bar'
            }
        }

        self.block_storage._BlockStorage__cull_tx(block)

        self.assertEqual('5a5bbc6c0388b5f76d9da11b39ed4df8c47b9d4c231c72bb09b1b5e689699e77', block.get('processed'))


    def test_PRIVATE_METHOD_write_block__stores_block_by_num(self):
        block = {
            'hash': '78238403271a8dcd3c1031b144ace7dfdbe760108f2953b85d40c763fc79e4d4',
            'number': '1658163894967101696',
            'hlc_timestamp': "2022-07-18T17:04:54.967101696Z_0",
            'processed': {
                'hash': '5a5bbc6c0388b5f76d9da11b39ed4df8c47b9d4c231c72bb09b1b5e689699e77',
                'foo': 'bar'
            }
        }

        self.block_storage._BlockStorage__write_block(block)

        filename = '1658163894967101696'.zfill(64)

        block_path = self.block_storage.block_driver.get_file_path(
            block_num=filename
        )

        with open(block_path) as f:
            b = json.loads(f.read())

        self.assertEqual(block, b)

    def test_PRIVATE_METHOD_write_block__stores_hash_symlink(self):
        block = {
            'hash': '78238403271a8dcd3c1031b144ace7dfdbe760108f2953b85d40c763fc79e4d4',
            'number': '1658163894967101696',
            'hlc_timestamp': "2022-07-18T17:04:54.967101696Z_0",
            'processed': {
                'hash': '5a5bbc6c0388b5f76d9da11b39ed4df8c47b9d4c231c72bb09b1b5e689699e77',
                'foo': 'bar'
            }
        }

        self.block_storage._BlockStorage__write_block(block)

        alias_dir = self.block_storage.block_alias_driver.get_directory(
            hash_str='78238403271a8dcd3c1031b144ace7dfdbe760108f2953b85d40c763fc79e4d4'
        )

        alias_path = os.path.join(alias_dir, '78238403271a8dcd3c1031b144ace7dfdbe760108f2953b85d40c763fc79e4d4')

        alias_link = os.readlink(alias_path)

        with open(alias_link) as f:
            ab = json.loads(f.read())

        self.assertEqual(ab, block)


    def test_PRIVATE_METHOD_write_txs__stores_transactions_by_hash_and_payload(self):
        block = {
            'hash': '78238403271a8dcd3c1031b144ace7dfdbe760108f2953b85d40c763fc79e4d4',
            'number': '1658163894967101696',
            'hlc_timestamp': "2022-07-18T17:04:54.967101696Z_0",
            'processed': {
                'hash': '5a5bbc6c0388b5f76d9da11b39ed4df8c47b9d4c231c72bb09b1b5e689699e77',
                'foo': 'bar'
            }
        }

        tx, tx_hash = self.block_storage._BlockStorage__cull_tx(block)

        self.block_storage._BlockStorage__write_tx(tx_hash=tx_hash, tx=tx)

        # Check transaction file
        tx_path = self.block_storage.tx_driver.get_directory(
            hash_str='5a5bbc6c0388b5f76d9da11b39ed4df8c47b9d4c231c72bb09b1b5e689699e77'
        )

        with open(os.path.join(tx_path, '5a5bbc6c0388b5f76d9da11b39ed4df8c47b9d4c231c72bb09b1b5e689699e77')) as f:
            t = json.loads(f.read())

        self.assertEqual(tx, t)

    def test_METHOD_store_block__stores_block_and_aliases(self):

        block = {
            'hash': '78238403271a8dcd3c1031b144ace7dfdbe760108f2953b85d40c763fc79e4d4',
            'number': '1658163894967101696',
            'hlc_timestamp': "2022-07-18T17:04:54.967101696Z_0",
            'processed': {
                'hash': '5a5bbc6c0388b5f76d9da11b39ed4df8c47b9d4c231c72bb09b1b5e689699e77',
                'foo': 'bar'
            }
        }

        self.block_storage.store_block(block)

        # Check transaction file
        tx_path = self.block_storage.tx_driver.get_directory(
            hash_str='5a5bbc6c0388b5f76d9da11b39ed4df8c47b9d4c231c72bb09b1b5e689699e77'
        )

        with open(os.path.join(tx_path, '5a5bbc6c0388b5f76d9da11b39ed4df8c47b9d4c231c72bb09b1b5e689699e77')) as f:
            t = json.loads(f.read())

        _t = {
            'hash': '5a5bbc6c0388b5f76d9da11b39ed4df8c47b9d4c231c72bb09b1b5e689699e77',
            'foo': 'bar'
        }

        self.assertEqual(t, _t)

        # Check Block Files
        block_path = self.block_storage.block_driver.get_file_path(
            block_num='1658163894967101696'.zfill(64)
        )

        with open(block_path) as f:
            b = json.loads(f.read())

        block['processed'] = '5a5bbc6c0388b5f76d9da11b39ed4df8c47b9d4c231c72bb09b1b5e689699e77'
        self.assertEqual(b, block)

        # Check Alias File
        alias_dir = self.block_storage.block_alias_driver.get_directory(
            hash_str='78238403271a8dcd3c1031b144ace7dfdbe760108f2953b85d40c763fc79e4d4'
        )

        alias_path = os.path.join(alias_dir, '78238403271a8dcd3c1031b144ace7dfdbe760108f2953b85d40c763fc79e4d4')

        alias_link = os.readlink(alias_path)

        with open(alias_link) as f:
            ab = json.loads(f.read())

        self.assertEqual(ab, block)


    def test_METHOD_get_block__returns_block_by_block_number(self):
        block = {
            'hash': '78238403271a8dcd3c1031b144ace7dfdbe760108f2953b85d40c763fc79e4d4',
            'number': '1658163894967101696',
            'hlc_timestamp': "2022-07-18T17:04:54.967101696Z_0",
            'processed': {
                'hash': '5a5bbc6c0388b5f76d9da11b39ed4df8c47b9d4c231c72bb09b1b5e689699e77',
            },
            'data': 'woop'
        }

        self.block_storage.store_block(deepcopy(block))

        got_block = self.block_storage.get_block(1658163894967101696)

        self.assertEqual(block, got_block)

    def test_METHOD_get_block__returns_block_by_block_hash(self):
        block = {
            'hash': '78238403271a8dcd3c1031b144ace7dfdbe760108f2953b85d40c763fc79e4d4',
            'number': '1658163894967101696',
            'hlc_timestamp': "2022-07-18T17:04:54.967101696Z_0",
            'processed': {
                'hash': '5a5bbc6c0388b5f76d9da11b39ed4df8c47b9d4c231c72bb09b1b5e689699e77',
            },
            'data': 'woop'
        }

        self.block_storage.store_block(deepcopy(block))

        got_block = self.block_storage.get_block('78238403271a8dcd3c1031b144ace7dfdbe760108f2953b85d40c763fc79e4d4')

        self.assertEqual(block, got_block)

    def test_METHOD_get_block__returns_block_by_hlc_timestamp(self):
        block = {
            'hash': '78238403271a8dcd3c1031b144ace7dfdbe760108f2953b85d40c763fc79e4d4',
            'number': '1658163894967101696',
            'hlc_timestamp': "2022-07-18T17:04:54.967101696Z_0",
            'processed': {
                'hash': '5a5bbc6c0388b5f76d9da11b39ed4df8c47b9d4c231c72bb09b1b5e689699e77',
            },
            'data': 'woop'
        }

        self.block_storage.store_block(deepcopy(block))

        got_block = self.block_storage.get_block("2022-07-18T17:04:54.967101696Z_0")

        self.assertEqual(block, got_block)

    def test_METHOD_get_block__cannot_find_hash_returns_None_block(self):
        block = {
            'hash': '78238403271a8dcd3c1031b144ace7dfdbe760108f2953b85d40c763fc79e4d4',
            'number': '1658163894967101696',
            'hlc_timestamp': "2022-07-18T17:04:54.967101696Z_0",
            'processed': {
                'hash': '5a5bbc6c0388b5f76d9da11b39ed4df8c47b9d4c231c72bb09b1b5e689699e77',
            },
            'data': 'woop'
        }

        self.block_storage.store_block(block)

        got_block = self.block_storage.get_block('b')

        self.assertIsNone(got_block)

    def test_METHOD_get_block__cannot_find_hlc_timestamp_returns_None_block(self):
        block = {
            'hash': '78238403271a8dcd3c1031b144ace7dfdbe760108f2953b85d40c763fc79e4d4',
            'number': '1658163894967101696',
            'hlc_timestamp': "2022-07-18T17:04:54.967101696Z_0",
            'processed': {
                'hash': '5a5bbc6c0388b5f76d9da11b39ed4df8c47b9d4c231c72bb09b1b5e689699e77',
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
            'hash': '78238403271a8dcd3c1031b144ace7dfdbe760108f2953b85d40c763fc79e4d4',
            'number': '1658163894967101696',
            'hlc_timestamp': "2022-07-18T17:04:54.967101696Z_0",
            'processed': {
                'hash': '5a5bbc6c0388b5f76d9da11b39ed4df8c47b9d4c231c72bb09b1b5e689699e77',
            },
            'data': 'woop'
        }

        self.block_storage.store_block(block)

        tx_got = self.block_storage.get_tx('5a5bbc6c0388b5f76d9da11b39ed4df8c47b9d4c231c72bb09b1b5e689699e77')

        self.assertIsNotNone(tx_got)
        self.assertEqual('5a5bbc6c0388b5f76d9da11b39ed4df8c47b9d4c231c72bb09b1b5e689699e77', tx_got.get('hash'))


    def test_METHOD_store_block__stores_txs_and_block(self):
        block = {
            'hash': '78238403271a8dcd3c1031b144ace7dfdbe760108f2953b85d40c763fc79e4d4',
            'number': '1658163894967101696',
            'hlc_timestamp': "2022-07-18T17:04:54.967101696Z_0",
            'processed': {
                'hash': '5a5bbc6c0388b5f76d9da11b39ed4df8c47b9d4c231c72bb09b1b5e689699e77',
                'foo': 'bar'
            }
        }

        self.block_storage.store_block(deepcopy(block))

        self.assertDictEqual(block.get('processed'), self.block_storage.get_tx(h='5a5bbc6c0388b5f76d9da11b39ed4df8c47b9d4c231c72bb09b1b5e689699e77'))

        self.assertDictEqual(block, self.block_storage.get_block('78238403271a8dcd3c1031b144ace7dfdbe760108f2953b85d40c763fc79e4d4'))
        self.assertDictEqual(block, self.block_storage.get_block(1658163894967101696))
        self.assertDictEqual(block, self.block_storage.get_block("2022-07-18T17:04:54.967101696Z_0"))

    def test_get_block_v_none_returns_none(self):
        self.assertIsNone(self.block_storage.get_block())

    def test_METHOD_remove_block__removes_block_and_block_alias_and_tx(self):
        block_number = '1658163894967101696'
        block_hash = '78238403271a8dcd3c1031b144ace7dfdbe760108f2953b85d40c763fc79e4d4'
        tx_hash = '5a5bbc6c0388b5f76d9da11b39ed4df8c47b9d4c231c72bb09b1b5e689699e77'
        block = {
            'hash': block_hash,
            'number': block_number,
            'hlc_timestamp': "2022-07-18T17:04:54.967101696Z_0",
            'processed': {
                'hash': tx_hash,
                'foo': 'bar'
            }
        }
        self.block_storage.store_block(deepcopy(block))

        block_path = self.block_storage.block_driver.get_file_path(block_num=block_number.zfill(64))
        block_alias_path = os.path.join(self.block_storage.block_alias_driver.get_directory(hash_str=block_hash), block_hash)
        tx_path = os.path.join(self.block_storage.tx_driver.get_directory(hash_str=tx_hash), tx_hash)

        # Assert the block was saved properly so we can validate they were removed later
        self.assertTrue(os.path.exists(block_path))
        self.assertTrue(os.path.exists(block_alias_path))
        self.assertTrue(os.path.exists(tx_path))

        # Remove block
        self.block_storage.remove_block(v=int(block_number))

        # Assert files are gone
        self.assertFalse(os.path.exists(block_path))
        self.assertFalse(os.path.exists(block_alias_path))
        self.assertFalse(os.path.exists(tx_path))

