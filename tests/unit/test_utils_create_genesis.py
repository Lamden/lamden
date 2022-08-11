from contracting.db.driver import FSDriver, TIME_KEY, Driver
from contracting.db.encoder import decode
from contracting.stdlib.bridge.time import Datetime
from lamden.crypto.block_validator import validate_block_structure
from lamden.storage import LATEST_BLOCK_HEIGHT_KEY, LATEST_BLOCK_HASH_KEY
from lamden.utils.create_genesis import main, GENESIS_CONTRACTS, GENESIS_BLOCK_PATH, build_genesis_contracts_changes
from pathlib import Path
from unittest import TestCase

SAMPLE_KEY = 'something.something'
SAMPLE_VAL = 'something'

class TestCreateGenesisBlock(TestCase):
    @classmethod
    def setUpClass(cls):
        TestCreateGenesisBlock.genesis_contracts_state_changes = build_genesis_contracts_changes()

    def setUp(self):
        self.founder_sk = 'beef' * 16
        self.earlier_time = Datetime(year=1, month=1, day=1)
        self.fsdriver = FSDriver(root=Path('/tmp/temp_filebased_state'))
        self.mongo_driver = Driver(db='test', collection='state')

        if GENESIS_BLOCK_PATH.is_file():
            GENESIS_BLOCK_PATH.unlink()
        self.fsdriver.flush()
        self.mongo_driver.flush()

    def tearDown(self):
        if GENESIS_BLOCK_PATH.is_file():
            GENESIS_BLOCK_PATH.unlink()
        self.fsdriver.flush()
        self.mongo_driver.flush()

    def create_filebased_state(self):
        for k, v in TestCreateGenesisBlock.genesis_contracts_state_changes.items():
            self.fsdriver.set(k, v)
        for contract in GENESIS_CONTRACTS:
            self.fsdriver.set(f'{contract}.{TIME_KEY}', self.earlier_time)
        self.fsdriver.set(SAMPLE_KEY, SAMPLE_VAL)

    def create_mongo_state(self):
        for k, v in TestCreateGenesisBlock.genesis_contracts_state_changes.items():
            self.mongo_driver.set(k, v)
        for contract in GENESIS_CONTRACTS:
            self.mongo_driver.set(f'{contract}.{TIME_KEY}', self.earlier_time)
        self.mongo_driver.set(SAMPLE_KEY, SAMPLE_VAL)

    def test_migration_scheme_none(self):
        main(self.founder_sk)

        self.assertTrue(GENESIS_BLOCK_PATH.is_file())
        with open(GENESIS_BLOCK_PATH) as f:
            genesis_block = decode(f.read())
        self.assertIsNotNone(genesis_block.get('genesis', None))
        self.assertGreater(len(genesis_block['genesis']), 0)

        actual_state_keys = [item['key'] for item in genesis_block['genesis']]
        expected_state_keys = list(TestCreateGenesisBlock.genesis_contracts_state_changes.keys()) + [LATEST_BLOCK_HASH_KEY, LATEST_BLOCK_HEIGHT_KEY]
        expected_state_keys.sort()

        self.assertListEqual(expected_state_keys, actual_state_keys)
        self.assertTrue(validate_block_structure(genesis_block))
        
    def test_migration_scheme_filesystem_preserves_existing_state_and_resubmits_genesis_contracts(self):
        self.create_filebased_state()

        main(self.founder_sk, migration_scheme='filesystem', filebased_state_path=self.fsdriver.root)

        self.assertTrue(GENESIS_BLOCK_PATH.is_file())
        with open(GENESIS_BLOCK_PATH) as f:
            genesis_block = decode(f.read())
        self.assertIsNotNone(genesis_block.get('genesis', None))
        self.assertGreater(len(genesis_block['genesis']), 0)

        actual_state_keys = [item['key'] for item in genesis_block['genesis']]
        expected_state_keys = self.fsdriver.keys() + [LATEST_BLOCK_HASH_KEY, LATEST_BLOCK_HEIGHT_KEY]
        expected_state_keys.sort()

        self.assertListEqual(expected_state_keys, actual_state_keys)
        self.assertTrue(validate_block_structure(genesis_block))
        for contract in GENESIS_CONTRACTS:
            self.assertGreater(next(item for item in genesis_block['genesis'] if item['key'] == f'{contract}.{TIME_KEY}')['value'], self.earlier_time)

    def test_migration_scheme_mongo_migrates_and_resubmits_genesis_contracts(self):
        self.create_mongo_state()

        main(self.founder_sk, migration_scheme='mongo', db='test', collection='state')

        self.assertTrue(GENESIS_BLOCK_PATH.is_file())
        with open(GENESIS_BLOCK_PATH) as f:
            genesis_block = decode(f.read())
        self.assertIsNotNone(genesis_block.get('genesis', None))
        self.assertGreater(len(genesis_block['genesis']), 0)

        actual_state_keys = [item['key'] for item in genesis_block['genesis']]
        expected_state_keys = self.mongo_driver.keys() + [LATEST_BLOCK_HASH_KEY, LATEST_BLOCK_HEIGHT_KEY]
        expected_state_keys.sort()

        self.assertListEqual(expected_state_keys, actual_state_keys)
        self.assertTrue(validate_block_structure(genesis_block))
        for contract in GENESIS_CONTRACTS:
            self.assertGreater(next(item for item in genesis_block['genesis'] if item['key'] == f'{contract}.{TIME_KEY}')['value'], self.earlier_time)