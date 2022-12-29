from contracting.client import ContractingClient
from contracting.db.driver import ContractDriver, FSDriver
from contracting.stdlib.bridge.time import Datetime
from datetime import datetime as dt
from lamden.contracts import sync
from pathlib import Path
from unittest import TestCase

class TestUpgrade(TestCase):
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
        self.assertEqual('v2.0.0', self.contract_driver.get('upgrade.S:lamden_tag'))
        self.assertEqual('v2.0.0', self.contract_driver.get('upgrade.S:contracting_tag'))

    def test_start_vote_updates_state_correctly(self):
        env = {'now': Datetime._from_datetime(dt.today())}
        self.upgrade.propose_upgrade(
            signer='mn01',
            lamden_tag='new',
            contracting_tag='new',
            environment=env
        )

        self.assertEqual('new', self.contract_driver.get('upgrade.vote_state:lamden_tag'))
        self.assertEqual('new', self.contract_driver.get('upgrade.vote_state:contracting_tag'))
        self.assertEqual(1, self.contract_driver.get('upgrade.vote_state:yays'))
        self.assertEqual(0, self.contract_driver.get('upgrade.vote_state:nays'))
        self.assertTrue(self.contract_driver.get('upgrade.vote_state:positions:mn01'))
        self.assertEqual(env['now'], self.contract_driver.get('upgrade.vote_state:started'))

    def test_propose_raises_if_invalid_voter(self):
        with self.assertRaises(AssertionError):
            self.upgrade.propose_upgrade(signer='mn04')

    def test_vote_raises_if_invalid_voter(self)dao:
        with self.assertRaises(AssertionError):
            self.upgrade.vote(signer='mn04')

    def test_vote_cannot_vote_twice(self):
        self.upgrade.propose_upgrade(
            signer='mn01', lamden_tag='new', contracting_tag='new'
        )

        with self.assertRaises(AssertionError):
            self.upgrade.vote(
                signer='mn01', position=True
            )

    def test_cannot_propose_while_another_vote_in_progress(self):
        self.upgrade.propose_upgrade(
            signer='mn01', lamden_tag='new', contracting_tag='new'
        )

        with self.assertRaises(AssertionError):
            self.upgrade.propose_upgrade(
                signer='mn01', lamden_tag='new', contracting_tag='new'
            )

    def test_vote_consensus_is_achieved(self):
        self.upgrade.propose_upgrade(
            signer='mn01', lamden_tag='new', contracting_tag='new'
        )

        self.upgrade.vote(signer='mn02', position=True)
        self.upgrade.vote(signer='mn03', position=True)

        self.assertEqual(self.contract_driver.get('upgrade.S:lamden_tag'), 'new')
        self.assertEqual(self.contract_driver.get('upgrade.S:contracting_tag'), 'new')

    def test_vote_dissent_consensus(self):
        self.upgrade.propose_upgrade(
            signer='mn01', lamden_tag='new', contracting_tag='new'
        )

        self.upgrade.vote(signer='mn02', position=True)
        self.upgrade.vote(signer='mn03', position=False)

        self.assertEqual(self.contract_driver.get('upgrade.S:lamden_tag'), 'v2.0.0')
        self.assertEqual(self.contract_driver.get('upgrade.S:contracting_tag'), 'v2.0.0')