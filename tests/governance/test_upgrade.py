from contracting.client import ContractingClient
from contracting.db.driver import ContractDriver, FSDriver
from contracting.stdlib.bridge.time import Datetime
from datetime import datetime as dt
from lamden.contracts import sync
from pathlib import Path
from unittest import TestCase

class TestCurrency(TestCase):
    def setUp(self):
        self.contract_driver = ContractDriver(driver=FSDriver(root=Path('/tmp/temp_filebased_state')))
        self.client = ContractingClient(driver=self.contract_driver)
        self.client.flush()

        sync.setup_genesis_contracts(initial_masternodes=['mn01', 'mn02', 'mn03'], client=self.client)

        self.election_house = self.client.get_contract('election_house')
        self.upgrade = self.client.get_contract('upgrade')

    def tearDown(self):
        self.client.flush()

    def test_seed_sets_initial_values_correctly(self):
        self.assertFalse(self.contract_driver.get('upgrade.upgrade_state:locked'))
        self.assertFalse(self.contract_driver.get('upgrade.upgrade_state:consensus'))
        self.assertEqual(0, self.contract_driver.get('upgrade.upgrade_state:votes'))
        self.assertEqual(0, self.contract_driver.get('upgrade.upgrade_state:voters'))

    def test_start_vote_updates_state_correctly(self):
        env = {'now': Datetime._from_datetime(dt.today())}
        self.upgrade.run_private_function(
            f='start_vote',
            lamden_branch_name='main',
            contracting_branch_name='main',
            pepper='pepper',
            environment=env
        )

        self.assertTrue(self.contract_driver.get('upgrade.upgrade_state:locked'))
        self.assertEqual('pepper', self.contract_driver.get('upgrade.upgrade_state:pepper'))
        self.assertEqual('main', self.contract_driver.get('upgrade.upgrade_state:lamden_branch_name'))
        self.assertEqual('main', self.contract_driver.get('upgrade.upgrade_state:contracting_branch_name'))
        self.assertEqual(0, self.contract_driver.get('upgrade.upgrade_state:votes'))
        self.assertEqual(3, self.contract_driver.get('upgrade.upgrade_state:voters'))
        self.assertEqual(env['now'], self.contract_driver.get('upgrade.upgrade_state:started'))

    def test_is_valid_voter(self):
        self.assertTrue(self.upgrade.run_private_function(f='is_valid_voter', address='mn01'))
        self.assertFalse(self.upgrade.run_private_function(f='is_valid_voter', address='mn04'))

    def test_vote_raises_if_invalid_voter(self):
        with self.assertRaises(AssertionError):
            self.upgrade.vote(signer='mn04')

    def test_vote_cannot_vote_twice(self):
        self.upgrade.vote(
            signer='mn01', lamden_branch_name='main', contracting_branch_name='main', pepper='pepper'
        )

        with self.assertRaises(AssertionError):
            self.upgrade.vote(signer='mn01')

    def test_vote_consensus_is_achieved(self):
        self.upgrade.vote(
            signer='mn01', lamden_branch_name='main', contracting_branch_name='main', pepper='pepper'
        )
        self.upgrade.vote(signer='mn02')

        self.assertTrue(self.contract_driver.get('upgrade.upgrade_state:consensus'))

    def test_vote_raises_if_voting_when_consensus_is_already_achieved(self):
        self.upgrade.vote(
            signer='mn01', lamden_branch_name='main', contracting_branch_name='main', pepper='pepper'
        )
        self.upgrade.vote(signer='mn02')
        
        with self.assertRaises(AssertionError):
            self.upgrade.vote(signer='mn03')
