from contracting.client import ContractingClient
from contracting.db.driver import ContractDriver, FSDriver
from contracting.stdlib.bridge.time import Datetime, Timedelta
from datetime import datetime as dt, timedelta as td
from lamden.contracts import sync
from lamden.crypto.wallet import Wallet
from pathlib import Path
from unittest import TestCase

class TestDAO(TestCase):
    def setUp(self):
        self.contract_driver = ContractDriver(driver=FSDriver(root=Path('/tmp/temp_filebased_state')))
        self.client = ContractingClient(driver=self.contract_driver)
        self.client.flush()

        self.members = [Wallet() for i in range(11)]
        sync.setup_genesis_contracts(initial_masternodes=[wallet.verifying_key for wallet in self.members],
                                     client=self.client)

        with open(sync.DEFAULT_PATH + '/genesis/dao.s.py') as f:
            self.client.submit(f.read(), name='dao', owner='election_house')

        self.election_house = self.client.get_contract(name='election_house')
        self.election_house.register_policy(contract='dao')
        self.dao = self.client.get_contract('dao')
        self.currency = self.client.get_contract(name='currency')

        self.contract_driver.set(key='currency.balances:dao', value=100_000_000)
        self.contract_driver.commit()

        self.total_votes_needed = (len(self.election_house.current_value_for_policy(policy='masternodes')) * 3 // 5) + 1
        self.specific_votes_needed = self.total_votes_needed * 7 // 10 + 1

    def tearDown(self):
        self.client.flush()

    def test_seed(self):
        self.assertListEqual(self.dao.quick_read('S', 'pending_motions'), [])
        self.assertEqual(self.dao.quick_read('S', 'yays'), 0)
        self.assertEqual(self.dao.quick_read('S', 'nays'), 0)
        self.assertIsNone(self.dao.quick_read('S', 'motion_start'))
        self.assertIsNone(self.dao.quick_read('S', 'recipient_vk'))
        self.assertIsNone(self.dao.quick_read('S', 'amount'))
        self.assertIsNone(self.dao.quick_read('S', 'positions'))
        self.assertEqual(self.dao.quick_read('S', 'motion_period'), Timedelta(days=1))
        self.assertEqual(self.dao.quick_read('S', 'motion_delay'), Timedelta(days=1))

    def test_vote_raises_if_not_called_from_election_house(self):
        with self.assertRaises(Exception):
            self.dao.vote(vk=self.members[0].verifying_key, obj=[])

    def test_vote_raises_if_caller_not_member(self):
        with self.assertRaises(AssertionError):
            self.election_house.vote(policy='dao', value=[])

    def test_vote_raises_if_args_list_invalid(self):
        with self.assertRaises(ValueError):
            self.election_house.vote(policy='dao', value=[], signer=self.members[0].verifying_key)

    def test_vote_raises_if_vk_is_invalid(self):
        with self.assertRaises(AssertionError):
            self.election_house.vote(policy='dao', value=['beef', 1], signer=self.members[0].verifying_key)
        with self.assertRaises(AssertionError):
            self.election_house.vote(policy='dao', value=[None, 1], signer=self.members[0].verifying_key)
        with self.assertRaises(AssertionError):
            self.election_house.vote(policy='dao', value=[123, 1], signer=self.members[0].verifying_key)
        with self.assertRaises(AssertionError):
            self.election_house.vote(policy='dao', value=[Wallet().verifying_key + 's', 1], signer=self.members[0].verifying_key)

    def test_vote_raises_if_amount_is_invalid(self):
        with self.assertRaises(AssertionError):
            self.election_house.vote(policy='dao', value=[Wallet().verifying_key, 0], signer=self.members[0].verifying_key)
        with self.assertRaises(AssertionError):
            self.election_house.vote(policy='dao', value=[Wallet().verifying_key, 'something'], signer=self.members[0].verifying_key)
        with self.assertRaises(AssertionError):
            self.election_house.vote(policy='dao', value=[Wallet().verifying_key, None], signer=self.members[0].verifying_key)

    def test_vote_starts_motion(self):
        recipient_vk = Wallet().verifying_key; amount = 100
        env = {'now': Datetime._from_datetime(dt.today())}

        self.election_house.vote(policy='dao', value=[recipient_vk, amount],
            signer=self.members[0].verifying_key, environment=env)

        self.assertEqual(self.dao.quick_read('S', 'motion_start'), env['now'])
        self.assertEqual(self.dao.quick_read('S', 'recipient_vk'), recipient_vk)
        self.assertEqual(self.dao.quick_read('S', 'amount'), amount)

    def test_vote_raises_if_vote_is_invalid_or_already_voted(self):
        recipient_vk = Wallet().verifying_key; amount = 100

        self.election_house.vote(policy='dao', value=[recipient_vk, amount], signer=self.members[0].verifying_key)
        with self.assertRaises(AssertionError):
            self.election_house.vote(policy='dao', value=['invalid_position'], signer=self.members[0].verifying_key)
        with self.assertRaises(ValueError):
            self.election_house.vote(policy='dao', value=[], signer=self.members[0].verifying_key)

        self.election_house.vote(policy='dao', value=[True], signer=self.members[0].verifying_key)

        self.assertEqual(self.dao.quick_read('S', 'yays'), 1)
        self.assertTrue(self.dao.quick_read('S', f'positions:{self.members[0].verifying_key}'))

        with self.assertRaises(AssertionError):
            self.election_house.vote(policy='dao', value=[True], signer=self.members[0].verifying_key)

    def test_vote_passes_motion_if_enough_yays_and_members_voted(self):
        recipient_vk = Wallet().verifying_key; amount = 100

        self.election_house.vote(policy='dao', value=[recipient_vk, amount], signer=self.members[0].verifying_key)

        for i in range(self.specific_votes_needed):
            self.election_house.vote(policy='dao', value=[True], signer=self.members[i].verifying_key)
        for i in range(self.specific_votes_needed, self.total_votes_needed):
            self.election_house.vote(policy='dao', value=[False], signer=self.members[i].verifying_key)

        self.assertEqual(len(self.election_house.current_value_for_policy(policy='dao')), 1)
        self.assertIsNotNone(self.dao.quick_read('S', 'pending_motions')[0]['motion_passed'])
        self.assertEqual(self.dao.quick_read('S', 'pending_motions')[0]['recipient_vk'], recipient_vk)
        self.assertEqual(self.dao.quick_read('S', 'pending_motions')[0]['amount'], amount)

        try:
            self.election_house.vote(policy='dao', value=[],
                environment={'now': Datetime._from_datetime(dt.today() + td(days=1))})
        except:
            pass

        self.assertEqual(self.contract_driver.get(f'currency.balances:{recipient_vk}'), amount)
        self.assertEqual(self.contract_driver.get('currency.balances:dao'), 100_000_000 - amount)
        self.assertListEqual(self.dao.quick_read('S', 'pending_motions'), [])
        self.assertEqual(self.dao.quick_read('S', 'yays'), 0)
        self.assertEqual(self.dao.quick_read('S', 'nays'), 0)
        self.assertIsNone(self.dao.quick_read('S', 'motion_start'))
        self.assertIsNone(self.dao.quick_read('S', 'recipient_vk'))
        self.assertIsNone(self.dao.quick_read('S', 'amount'))
        self.assertIsNone(self.dao.quick_read('S', 'positions'))

    def test_vote_skips_motion_if_enough_nays_and_menbers_voted(self):
        recipient_vk = Wallet().verifying_key; amount = 100

        self.election_house.vote(policy='dao', value=[recipient_vk, amount], signer=self.members[0].verifying_key)

        for i in range(self.specific_votes_needed):
            self.election_house.vote(policy='dao', value=[False], signer=self.members[i].verifying_key)
        for i in range(self.specific_votes_needed, self.total_votes_needed):
            self.election_house.vote(policy='dao', value=[True], signer=self.members[i].verifying_key)

        self.assertIsNone(self.contract_driver.get(f'currency.balances:{recipient_vk}'))
        self.assertEqual(self.contract_driver.get('currency.balances:dao'), 100_000_000)
        self.assertListEqual(self.election_house.current_value_for_policy(policy='dao'), [])
        self.assertEqual(self.dao.quick_read('S', 'yays'), 0)
        self.assertEqual(self.dao.quick_read('S', 'nays'), 0)
        self.assertIsNone(self.dao.quick_read('S', 'motion_start'))
        self.assertIsNone(self.dao.quick_read('S', 'recipient_vk'))
        self.assertIsNone(self.dao.quick_read('S', 'amount'))
        self.assertIsNone(self.dao.quick_read('S', 'positions'))
        self.assertEqual(self.dao.quick_read('S', 'motion_period'), Timedelta(days=1))
        self.assertEqual(self.dao.quick_read('S', 'motion_delay'), Timedelta(days=1))

    def test_vote_skips_motion_if_motion_expired(self):
        recipient_vk = Wallet().verifying_key; amount = 100

        self.election_house.vote(policy='dao', value=[recipient_vk, amount], signer=self.members[0].verifying_key)

        self.election_house.vote(policy='dao', value=[True], signer=self.members[0].verifying_key,
            environment={'now': Datetime._from_datetime(dt.today() + td(days=1))})

        self.assertIsNone(self.contract_driver.get(f'currency.balances:{recipient_vk}'))
        self.assertEqual(self.contract_driver.get('currency.balances:dao'), 100_000_000)
        self.assertListEqual(self.election_house.current_value_for_policy(policy='dao'), [])
        self.assertEqual(self.dao.quick_read('S', 'yays'), 0)
        self.assertEqual(self.dao.quick_read('S', 'nays'), 0)
        self.assertIsNone(self.dao.quick_read('S', 'motion_start'))
        self.assertIsNone(self.dao.quick_read('S', 'recipient_vk'))
        self.assertIsNone(self.dao.quick_read('S', 'amount'))
        self.assertIsNone(self.dao.quick_read('S', 'positions'))
        self.assertEqual(self.dao.quick_read('S', 'motion_period'), Timedelta(days=1))
        self.assertEqual(self.dao.quick_read('S', 'motion_delay'), Timedelta(days=1))

    def test_pass_motion(self):
        self.dao.S['recipient_vk'] = Wallet().verifying_key
        self.dao.S['amount'] = 100

        self.dao.run_private_function(f='pass_motion', signer='election_house')

        self.assertEqual(len(self.election_house.current_value_for_policy(policy='dao')), 1)
        self.assertEqual(self.dao.quick_read('S', 'yays'), 0)
        self.assertEqual(self.dao.quick_read('S', 'nays'), 0)
        self.assertIsNone(self.dao.quick_read('S', 'motion_start'))
        self.assertIsNone(self.dao.quick_read('S', 'recipient_vk'))
        self.assertIsNone(self.dao.quick_read('S', 'amount'))
        self.assertIsNone(self.dao.quick_read('S', 'positions'))
        self.assertEqual(self.dao.quick_read('S', 'motion_period'), Timedelta(days=1))
        self.assertEqual(self.dao.quick_read('S', 'motion_delay'), Timedelta(days=1))

    def test_finalize_pending_motion(self):
        recipient_vk = Wallet().verifying_key; amount = 100
        self.dao.S['recipient_vk'] = recipient_vk
        self.dao.S['amount'] = amount
        self.dao.run_private_function(f='pass_motion', signer='election_house')

        self.dao.run_private_function(f='finalize_pending_motions', signer='election_house',
            environment={'now': Datetime._from_datetime(dt.today() + td(days=1))})

        self.assertListEqual(self.election_house.current_value_for_policy(policy='dao'), [])
        self.assertEqual(self.contract_driver.get(f'currency.balances:{recipient_vk}'), amount)
        self.assertEqual(self.contract_driver.get('currency.balances:dao'), 100_000_000 - amount)
