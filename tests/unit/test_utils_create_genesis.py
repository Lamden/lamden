from contracting.client import ContractingClient
from contracting.db.driver import FSDriver, ContractDriver, TIME_KEY, Driver
from contracting.db.encoder import decode
from contracting.stdlib.bridge.time import Datetime
from lamden.contracts import sync
from lamden.crypto.block_validator import validate_block_structure
from lamden.storage import LATEST_BLOCK_HEIGHT_KEY, LATEST_BLOCK_HASH_KEY
from lamden.utils.create_genesis import main, setup_genesis_contracts, GENESIS_CONTRACTS, GENESIS_STATE_PATH, GENESIS_BLOCK_PATH
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
import json
import shutil

SAMPLE_KEY = 'something.something'
SAMPLE_VAL = 'something'

class TestCreateGenesisBlock(TestCase):
    @classmethod
    def setUpClass(cls):
        TestCreateGenesisBlock.genesis_contracts_state_changes = {}

        TestCreateGenesisBlock.other_state = FSDriver(Path().home().joinpath('test'))
        other_contract_driver = ContractDriver(driver=TestCreateGenesisBlock.other_state)
        other_contracting_client = ContractingClient(driver=other_contract_driver, submission_filename=sync.DEFAULT_SUBMISSION_PATH)
        other_contracting_client.set_submission_contract(filename=sync.DEFAULT_SUBMISSION_PATH, commit=False)
        TestCreateGenesisBlock.genesis_contracts_state_changes.update(other_contracting_client.raw_driver.pending_writes)
        other_contracting_client.raw_driver.commit()
        other_contracting_client.submission_contract = other_contracting_client.get_contract('submission')

        constitution = None
        with open(Path.home().joinpath('constitution.json')) as f:
            constitution = json.load(f)

        sync.setup_genesis_contracts(
            initial_masternodes=[vk for vk in constitution['masternodes'].keys()],
            initial_delegates=[vk for vk in constitution['delegates'].keys()],
            client=other_contracting_client,
            commit=False
        )
        TestCreateGenesisBlock.genesis_contracts_state_changes.update(other_contracting_client.raw_driver.pending_writes)
        TestCreateGenesisBlock.genesis_contracts_state_changes = {k: v for k, v in TestCreateGenesisBlock.genesis_contracts_state_changes.items() if v is not None}
        other_contracting_client.raw_driver.commit()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(Path().home().joinpath('test'))

    def setUp(self):
        self.founder_sk = 'beef' * 16
        self.state = FSDriver(root=GENESIS_STATE_PATH)
        self.contract_driver = ContractDriver(driver=self.state)
        self.contracting_client = ContractingClient(driver=self.contract_driver, submission_filename=sync.DEFAULT_SUBMISSION_PATH)
        self.earlier_time = Datetime(year=1, month=1, day=1)

        if GENESIS_BLOCK_PATH.is_file():
            GENESIS_BLOCK_PATH.unlink()

    def tearDown(self):
        GENESIS_BLOCK_PATH.unlink()

    def test_migration_scheme_none(self):
        main(self.founder_sk, 'none', self.contracting_client)

        self.assertTrue(GENESIS_BLOCK_PATH.is_file())
        with open(GENESIS_BLOCK_PATH) as f:
            genesis_block = decode(f.read())
        self.assertIsNotNone(genesis_block.get('genesis', None))
        self.assertGreater(len(genesis_block['genesis']), 0)

        actual_state_keys = [item['key'] for item in genesis_block['genesis']]
        actual_state_keys.sort()

        expected_state_keys = list(TestCreateGenesisBlock.genesis_contracts_state_changes.keys()) + [LATEST_BLOCK_HASH_KEY, LATEST_BLOCK_HEIGHT_KEY]
        expected_state_keys.sort()
        self.assertListEqual(expected_state_keys, actual_state_keys)
        self.assertTrue(validate_block_structure(genesis_block))
        
    def test_migration_scheme_filesystem_preserves_existing_state_and_resubmits_genesis_contracts(self):
        for contract in GENESIS_CONTRACTS:
            TestCreateGenesisBlock.other_state.set(f'{contract}.{TIME_KEY}', self.earlier_time)
        TestCreateGenesisBlock.other_state.set(SAMPLE_KEY, SAMPLE_VAL)

        main(self.founder_sk, 'filesystem', self.contracting_client, existing_state_driver=TestCreateGenesisBlock.other_state)

        self.assertTrue(GENESIS_BLOCK_PATH.is_file())
        with open(GENESIS_BLOCK_PATH) as f:
            genesis_block = decode(f.read())
        self.assertIsNotNone(genesis_block.get('genesis', None))
        self.assertGreater(len(genesis_block['genesis']), 0)

        actual_state_keys = [item['key'] for item in genesis_block['genesis']]
        expected_state_keys = list(TestCreateGenesisBlock.genesis_contracts_state_changes.keys()) + [LATEST_BLOCK_HASH_KEY, LATEST_BLOCK_HEIGHT_KEY, SAMPLE_KEY]
        actual_state_keys.sort()
        expected_state_keys.sort()

        self.assertListEqual(expected_state_keys, actual_state_keys)
        self.assertTrue(validate_block_structure(genesis_block))
        for contract in GENESIS_CONTRACTS:
            self.assertGreater(next(item for item in genesis_block['genesis'] if item['key'] == f'{contract}.{TIME_KEY}')['value'], self.earlier_time)

    def test_migration_scheme_mongo_migrates_and_resubmits_genesis_contracts(self):
        mongo_driver = Driver(db='test', collection='test')
        mongo_driver.flush()
        contracting_client = ContractingClient(driver=ContractDriver(driver=mongo_driver), submission_filename=sync.DEFAULT_SUBMISSION_PATH)
        setup_genesis_contracts(contracting_client)
        mongo_driver.set(SAMPLE_KEY, SAMPLE_VAL)
        for contract in GENESIS_CONTRACTS:
            mongo_driver.set(f'{contract}.{TIME_KEY}', self.earlier_time)

        main(self.founder_sk, 'mongo', self.contracting_client, db='test', collection='test')

        self.assertTrue(GENESIS_BLOCK_PATH.is_file())
        with open(GENESIS_BLOCK_PATH) as f:
            genesis_block = decode(f.read())
        self.assertIsNotNone(genesis_block.get('genesis', None))
        self.assertGreater(len(genesis_block['genesis']), 0)

        actual_state_keys = [item['key'] for item in genesis_block['genesis']]
        expected_state_keys = mongo_driver.keys() + [LATEST_BLOCK_HASH_KEY, LATEST_BLOCK_HEIGHT_KEY]
        actual_state_keys.sort()
        expected_state_keys.sort()

        self.assertListEqual(expected_state_keys, actual_state_keys)
        self.assertTrue(validate_block_structure(genesis_block))
        for contract in GENESIS_CONTRACTS:
            self.assertGreater(next(item for item in genesis_block['genesis'] if item['key'] == f'{contract}.{TIME_KEY}')['value'], self.earlier_time)