from contracting.client import ContractingClient
from contracting.db.driver import FSDriver, ContractDriver
from lamden.contracts import sync
from lamden.storage import BlockStorage, STORAGE_HOME
from lamden.utils.create_genesis import main
from unittest import TestCase
from unittest.mock import patch
from pathlib import Path
import json

class TestCreateGenesisBlock(TestCase):
    def setUpClass():
        other_state = FSDriver(STORAGE_HOME.joinpath('test'))
        other_contract_driver = ContractDriver(driver=other_state)
        other_contracting_client = ContractingClient(driver=other_contract_driver, submission_filename=sync.DEFAULT_SUBMISSION_PATH)
        other_contracting_client.set_submission_contract(commit=False)

        constitution = None
        with open(Path.home().joinpath('constitution.json')) as f:
            constitution = json.load(f)
        sync.setup_genesis_contracts(
            initial_masternodes=constitution['masternodes'],
            initial_delegates=constitution['delegates'],
            client=other_contracting_client,
            commit=False
        )

        TestCreateGenesisBlock.genesis_contracts_state_changes = {
            k: v for k, v in other_contract_driver.pending_writes.items() if v is not None
        }

    def setUp(self):
        self.founder_sk = 'beefbeefbeefbeefbeefbeefbeefbeefbeefbeefbeefbeefbeefbeefbeefbeef'
        self.bs = BlockStorage()
        self.state = FSDriver()
        self.contract_driver = ContractDriver(driver=self.state)
        self.contracting_client = ContractingClient(driver=self.contract_driver, submission_filename=sync.DEFAULT_SUBMISSION_PATH)

        self.bs.flush()
        self.state.flush()

    def tearDown(self):
        self.bs.flush()
        self.state.flush()

    @patch('lamden.utils.create_genesis.confirm_and_flush_blocks', return_value=True)
    @patch('lamden.utils.create_genesis.confirm_and_flush_state', return_value=True)
    def test_migration_scheme_none(self, flush_blocks, flush_state):
        main(self.founder_sk, 'none', self.bs, self.state, self.contract_driver, self.contracting_client)

        genesis_block = self.bs.get_genesis_block()
        self.assertIsNotNone(genesis_block)
        gen_block_state_keys = [item['key'] for item in genesis_block['genesis']]
    
        for key in TestCreateGenesisBlock.genesis_contracts_state_changes:
            self.assertIn(key, gen_block_state_keys)
            self.assertIsNotNone(self.state.get(key))
        
    @patch('lamden.utils.create_genesis.confirm_and_flush_blocks', return_value=True)
    def test_migration_scheme_filesystem(self, flush_blocks):
        pass

    @patch('lamden.utils.create_genesis.confirm_and_flush_blocks', return_value=True)
    @patch('lamden.utils.create_genesis.confirm_and_flush_state', return_value=True)
    def test_migration_scheme_mongo(self):
        pass
