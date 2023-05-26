from contracting.client import ContractingClient
from contracting.db.driver import FSDriver, TIME_KEY, Driver, ContractDriver
from contracting.db.encoder import decode
from contracting.stdlib.bridge.time import Datetime
from lamden.contracts import sync
from lamden.crypto.block_validator import validate_block_structure
from lamden.utils import create_genesis
from pathlib import Path
from unittest import TestCase
import json
import os
import shutil

SAMPLE_KEY = 'something.something'
SAMPLE_VAL = 'something'

class TestCreateGenesisBlock(TestCase):
    @classmethod
    def setUpClass(cls):
        TestCreateGenesisBlock.genesis_contracts_state_changes = create_genesis.build_genesis_contracts_changes()

    def setUp(self):
        self.root = './.lamden'
        self.create_directories()

        self.founder_sk = 'beef' * 16
        self.earlier_time = Datetime(year=1, month=1, day=1)
        self.fsdriver = FSDriver(root=self.root)
        self.db = 'test'
        self.collection = 'state'
        self.mongo_driver = Driver(db=self.db, collection=self.collection)

        if create_genesis.GENESIS_BLOCK_PATH.is_file():
            create_genesis.GENESIS_BLOCK_PATH.unlink()

        self.fsdriver.flush()
        self.mongo_driver.flush()

    def tearDown(self):
        if create_genesis.GENESIS_BLOCK_PATH.is_file():
            create_genesis.GENESIS_BLOCK_PATH.unlink()
        self.fsdriver.flush()
        self.mongo_driver.flush()

    def create_directories(self):
        if os.path.exists(Path(self.root)):
            shutil.rmtree(Path(self.root))

        os.makedirs(Path(self.root))

    def create_filebased_state(self):
        for k, v in TestCreateGenesisBlock.genesis_contracts_state_changes.items():
            self.fsdriver.set(k, v)

        for contract in create_genesis.GENESIS_CONTRACTS:
            if contract != 'submission':
                self.fsdriver.set(f'{contract}.{TIME_KEY}', self.earlier_time)

        self.fsdriver.set(SAMPLE_KEY, SAMPLE_VAL)

    def create_mongo_state(self):
        for k, v in TestCreateGenesisBlock.genesis_contracts_state_changes.items():
            self.mongo_driver.set(k, v)
        for contract in create_genesis.GENESIS_CONTRACTS:
            if contract != 'submission':
                self.mongo_driver.set(f'{contract}.{TIME_KEY}', self.earlier_time)
        self.mongo_driver.set(SAMPLE_KEY, SAMPLE_VAL)

    def test_build_genesis_contracts_state_changes(self):
        state_changes = {}
        contracting_client = ContractingClient(driver=ContractDriver(self.fsdriver), submission_filename=sync.DEFAULT_SUBMISSION_PATH)

        contracting_client.set_submission_contract(filename=sync.DEFAULT_SUBMISSION_PATH, commit=False)
        state_changes.update(contracting_client.raw_driver.pending_writes)

        contracting_client.raw_driver.commit()
        contracting_client.submission_contract = contracting_client.get_contract('submission')

        constitution = None
        with open(Path.home().joinpath('constitution.json')) as f:
            constitution = json.load(f)

        sync.setup_genesis_contracts(
            initial_masternodes=[vk for vk in constitution['masternodes'].keys()],
            client=contracting_client,
            commit=False
        )

        state_changes.update(contracting_client.raw_driver.pending_writes)
        contracting_client.flush()

        state_changes = {k: v for k, v in state_changes.items() if v is not None}

        self.assertListEqual(list(TestCreateGenesisBlock.genesis_contracts_state_changes.keys()), list(state_changes.keys()))

    def test_fetch_filebased_state(self):
        self.create_filebased_state()

        expected_result = list(TestCreateGenesisBlock.genesis_contracts_state_changes.keys())
        expected_result.sort()
        actual_result = list(create_genesis.fetch_filebased_state(self.fsdriver.root, ignore_keys=[SAMPLE_KEY]).keys())

        self.assertListEqual(actual_result, expected_result)

        expected_result.append(SAMPLE_KEY)
        expected_result.sort()
        actual_result = list(create_genesis.fetch_filebased_state(self.fsdriver.root).keys())

        self.assertListEqual(actual_result, expected_result)

    def test_fetch_mongo_state(self):
        self.create_mongo_state()

        expected_result = list(TestCreateGenesisBlock.genesis_contracts_state_changes.keys())
        expected_result.sort()
        actual_result = list(create_genesis.fetch_mongo_state(self.db, self.collection, ignore_keys=[SAMPLE_KEY]).keys())
        actual_result.sort()

        self.assertListEqual(actual_result, expected_result)

        expected_result.append(SAMPLE_KEY)
        expected_result.sort()
        actual_result = list(create_genesis.fetch_mongo_state(self.db, self.collection).keys())
        actual_result.sort()

        self.assertListEqual(actual_result, expected_result)

    def test_build_block_no_additional_state(self):
        genesis_block = create_genesis.build_block(self.founder_sk)

        self.assertIsNotNone(genesis_block.get('genesis', None))
        self.assertGreater(len(genesis_block['genesis']), 0)

        actual_state_keys = [item['key'] for item in genesis_block['genesis']]
        expected_state_keys = list(TestCreateGenesisBlock.genesis_contracts_state_changes.keys())
        expected_state_keys.sort()

        self.assertListEqual(expected_state_keys, actual_state_keys)
        self.assertTrue(validate_block_structure(genesis_block))

    def test_build_block_with_additional_state(self):
        genesis_block = create_genesis.build_block(self.founder_sk, additional_state={SAMPLE_KEY: SAMPLE_VAL})

        self.assertIsNotNone(genesis_block.get('genesis', None))
        self.assertGreater(len(genesis_block['genesis']), 0)

        actual_state_keys = [item['key'] for item in genesis_block['genesis']]
        expected_state_keys = list(TestCreateGenesisBlock.genesis_contracts_state_changes.keys()) + [SAMPLE_KEY]
        expected_state_keys.sort()

        self.assertListEqual(expected_state_keys, actual_state_keys)
        self.assertTrue(validate_block_structure(genesis_block))

    def test_main_fails_if_genesis_block_file_exists(self):
        open(create_genesis.GENESIS_BLOCK_PATH, 'a').close()
        with self.assertRaises(AssertionError):
            create_genesis.main(self.founder_sk)

    def test_main_migration_scheme_none(self):
        create_genesis.main(self.founder_sk)

        self.assertTrue(create_genesis.GENESIS_BLOCK_PATH.is_file())
        with open(create_genesis.GENESIS_BLOCK_PATH) as f:
            genesis_block = decode(f.read())
        self.assertIsNotNone(genesis_block.get('genesis', None))
        self.assertGreater(len(genesis_block['genesis']), 0)

        actual_state_keys = [item['key'] for item in genesis_block['genesis']]
        expected_state_keys = list(TestCreateGenesisBlock.genesis_contracts_state_changes.keys())
        expected_state_keys.sort()

        self.assertListEqual(expected_state_keys, actual_state_keys)
        self.assertTrue(validate_block_structure(genesis_block))
        
    def test_main_migration_scheme_filesystem_preserves_existing_state_and_resubmits_genesis_contracts(self):
        self.create_filebased_state()

        create_genesis.main(self.founder_sk, migration_scheme='filesystem', filebased_state_path=self.fsdriver.root)

        self.assertTrue(create_genesis.GENESIS_BLOCK_PATH.is_file())
        with open(create_genesis.GENESIS_BLOCK_PATH) as f:
            genesis_block = decode(f.read())
        self.assertIsNotNone(genesis_block.get('genesis', None))
        self.assertGreater(len(genesis_block['genesis']), 0)

        actual_state_keys = [item['key'] for item in genesis_block['genesis']]
        expected_state_keys = self.fsdriver.keys()
        expected_state_keys.sort()

        self.assertListEqual(expected_state_keys, actual_state_keys)
        self.assertTrue(validate_block_structure(genesis_block))
        for contract in create_genesis.GENESIS_CONTRACTS:
            if contract != 'submission':
                self.assertGreater(next(item for item in genesis_block['genesis'] if item['key'] == f'{contract}.{TIME_KEY}')['value'], self.earlier_time)

    def test_main_migration_scheme_mongo_migrates_and_resubmits_genesis_contracts(self):
        self.create_mongo_state()

        create_genesis.main(self.founder_sk, migration_scheme='mongo', db='test', collection='state')

        self.assertTrue(create_genesis.GENESIS_BLOCK_PATH.is_file())
        with open(create_genesis.GENESIS_BLOCK_PATH) as f:
            genesis_block = decode(f.read())
        self.assertIsNotNone(genesis_block.get('genesis', None))
        self.assertGreater(len(genesis_block['genesis']), 0)

        actual_state_keys = [item['key'] for item in genesis_block['genesis']]
        expected_state_keys = self.mongo_driver.keys()
        expected_state_keys.sort()

        self.assertListEqual(expected_state_keys, actual_state_keys)
        self.assertTrue(validate_block_structure(genesis_block))
        for contract in create_genesis.GENESIS_CONTRACTS:
            if contract != 'submission':
                self.assertGreater(next(item for item in genesis_block['genesis'] if item['key'] == f'{contract}.{TIME_KEY}')['value'], self.earlier_time)
