from contracting.client import ContractingClient
from contracting.db.driver import FSDriver, ContractDriver, TIME_KEY, Driver
from contracting.stdlib.bridge.time import Datetime
from lamden.contracts import sync
from lamden.crypto.block_validator import validate_block_structure
from lamden.storage import BlockStorage, LATEST_BLOCK_HEIGHT_KEY, LATEST_BLOCK_HASH_KEY
from lamden.utils.create_genesis import main, setup_genesis_contracts, GENESIS_CONTRACTS
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
        other_state = FSDriver(Path().home().joinpath('test'))
        other_contract_driver = ContractDriver(driver=other_state)
        other_contracting_client = ContractingClient(driver=other_contract_driver, submission_filename=sync.DEFAULT_SUBMISSION_PATH)
        other_contracting_client.set_submission_contract(commit=False)

        constitution = None
        with open(Path.home().joinpath('constitution.json')) as f:
            constitution = json.load(f)

        sync.setup_genesis_contracts(
            initial_masternodes=[vk for vk in constitution['masternodes'].keys()],
            initial_delegates=[vk for vk in constitution['delegates'].keys()],
            client=other_contracting_client,
            commit=False
        )

        TestCreateGenesisBlock.genesis_contracts_state_changes = {
            k: v for k, v in other_contract_driver.pending_writes.items() if v is not None
        }

    def setUp(self):

        self.founder_sk = 'beef' * 16

        self.current_path = Path.cwd()
        self.temp_storage = Path(f'{self.current_path}/temp_storage')

        try:
            shutil.rmtree(self.temp_storage)
        except FileNotFoundError:
            pass
        self.temp_storage.mkdir(exist_ok=True, parents=True)

        self.bs = BlockStorage(root=self.temp_storage)
        self.state = FSDriver(root=Path(f'{self.temp_storage}/state'))

        self.contract_driver = ContractDriver(driver=self.state)
        self.contracting_client = ContractingClient(driver=self.contract_driver, submission_filename=sync.DEFAULT_SUBMISSION_PATH)
        self.earlier_time = Datetime(year=1, month=1, day=1)

        self.bs.flush()
        self.state.flush()

    def tearDown(self):
        self.bs.flush()
        self.state.flush()

    @patch('lamden.utils.create_genesis.confirm_and_flush_blocks', return_value=True)
    @patch('lamden.utils.create_genesis.confirm_and_flush_state', return_value=True)
    def test_migration_scheme_none(self, flush_blocks, flush_state):
        main(self.founder_sk, 'none', self.bs, self.state, self.contract_driver, self.contracting_client)

        genesis_block = self.bs.get_block(0)
        self.assertIsNotNone(genesis_block)
        gen_block_state_keys = [item['key'] for item in genesis_block['genesis']]

        self.assertEqual(self.state.get(LATEST_BLOCK_HEIGHT_KEY),  genesis_block['number'])
        self.assertEqual(self.state.get(LATEST_BLOCK_HASH_KEY),  genesis_block['hash'])
        for key in TestCreateGenesisBlock.genesis_contracts_state_changes:
            self.assertIn(key, gen_block_state_keys)
            self.assertIsNotNone(self.state.get(key))
        self.assertTrue(validate_block_structure(genesis_block))
        
    @patch('lamden.utils.create_genesis.confirm_and_flush_blocks', return_value=True)
    def test_migration_scheme_filesystem_preserves_existing_state_and_resubmits_genesis_contracts(self, flush_blocks):
        self.state.set(SAMPLE_KEY, SAMPLE_VAL)
        setup_genesis_contracts(self.contracting_client)
        for contract in GENESIS_CONTRACTS:
            self.state.set(f'{contract}.{TIME_KEY}', self.earlier_time)

        main(self.founder_sk, 'filesystem', self.bs, self.state, self.contract_driver, self.contracting_client)

        genesis_block = self.bs.get_block(0)
        self.assertIsNotNone(genesis_block)
        gen_block_state_keys = [item['key'] for item in genesis_block['genesis']]

        self.assertEqual(self.state.get(LATEST_BLOCK_HEIGHT_KEY),  genesis_block['number'])
        self.assertEqual(self.state.get(LATEST_BLOCK_HASH_KEY),  genesis_block['hash'])
        for key in TestCreateGenesisBlock.genesis_contracts_state_changes:
            self.assertIn(key, gen_block_state_keys)
            self.assertIsNotNone(self.state.get(key))
        self.assertTrue(validate_block_structure(genesis_block))

        self.assertEqual(self.state.get(SAMPLE_KEY), SAMPLE_VAL)
        self.assertIn(SAMPLE_KEY, gen_block_state_keys)
        for contract in GENESIS_CONTRACTS:
            self.assertGreater(self.state.get(f'{contract}.{TIME_KEY}'), self.earlier_time)

    @patch('lamden.utils.create_genesis.confirm_and_flush_blocks', return_value=True)
    @patch('lamden.utils.create_genesis.confirm_and_flush_state', return_value=True)
    def test_migration_scheme_mongo_migrates_and_resubmits_genesis_contracts(self, flush_blocks, flush_state):
        mongod = Driver(db='test', collection='test')
        mongod.set(SAMPLE_KEY, SAMPLE_VAL)
        for contract in GENESIS_CONTRACTS:
            mongod.set(f'{contract}.{TIME_KEY}', self.earlier_time)

        main(self.founder_sk, 'mongo', self.bs, self.state, self.contract_driver, self.contracting_client, db='test', collection='test')

        genesis_block = self.bs.get_block(0)
        self.assertIsNotNone(genesis_block)
        gen_block_state_keys = [item['key'] for item in genesis_block['genesis']]

        self.assertEqual(self.state.get(LATEST_BLOCK_HEIGHT_KEY),  genesis_block['number'])
        self.assertEqual(self.state.get(LATEST_BLOCK_HASH_KEY),  genesis_block['hash'])
        for key in TestCreateGenesisBlock.genesis_contracts_state_changes:
            self.assertIn(key, gen_block_state_keys)
            self.assertIsNotNone(self.state.get(key))
        self.assertTrue(validate_block_structure(genesis_block))

        self.assertEqual(self.state.get(SAMPLE_KEY), SAMPLE_VAL)
        self.assertIn(SAMPLE_KEY, gen_block_state_keys)
        for contract in GENESIS_CONTRACTS:
            self.assertGreater(self.state.get(f'{contract}.{TIME_KEY}'), mongod.get(f'{contract}.{TIME_KEY}'))
