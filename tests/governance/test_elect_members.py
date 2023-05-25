from contracting.client import ContractingClient
from contracting.db.driver import ContractDriver, FSDriver
from contracting.stdlib.bridge.time import Datetime
from datetime import datetime as dt, timedelta as td
from lamden.contracts import sync
from pathlib import Path
import os
from unittest import TestCase

class TestPendingMasters(TestCase):
    def setUp(self):
        submission_file_path = os.path.join(Path.cwd().parent, 'integration', 'mock', 'submission.py')
        self.contract_driver = ContractDriver(driver=FSDriver(root=Path('/tmp/temp_filebased_state')))
        self.client = ContractingClient(driver=self.contract_driver, submission_filename=submission_file_path)
        self.client.flush()

        sync.setup_genesis_contracts(initial_masternodes=['stux', 'raghu'], client=self.client)

        self.elect_masternodes = self.client.get_contract(name='elect_masternodes')
        self.currency = self.client.get_contract(name='currency')
        self.masternodes = self.client.get_contract(name='masternodes')
        self.stamp_cost = self.client.get_contract(name='stamp_cost')
        self.election_house = self.client.get_contract(name='election_house')

        self.contract_driver.set(key='currency.balances:stu', value=100_000_000)
        self.contract_driver.set(key='currency.balances:raghu', value=100_000_000)
        self.contract_driver.commit()

    def tearDown(self):
        self.client.flush()

    def test_register(self):
        self.currency.approve(signer='stu', amount=100_000, to='elect_masternodes')
        self.elect_masternodes.register(signer='stu')
        q = self.elect_masternodes.candidate_state['votes', 'stu']

        self.assertEqual(q, 0)
        self.assertEqual(self.currency.balances['elect_masternodes'], 100_000)
        self.assertEqual(self.elect_masternodes.candidate_state['registered', 'stu'], True)

    def test_double_register_raises_assert(self):
        self.currency.approve(signer='stu', amount=100_000, to='elect_masternodes')
        self.elect_masternodes.register(signer='stu')
        self.currency.approve(signer='stu', amount=100_000, to='elect_masternodes')

        with self.assertRaises(AssertionError):
            self.elect_masternodes.register(signer='stu')

# TODO
#    def test_unregister_returns_currency(self):
#        b1 = self.currency.balances['stu']
#        self.currency.approve(signer='stu', amount=100_000, to='elect_masternodes')
#        self.elect_masternodes.register(signer='stu')
#
#        self.assertEqual(self.currency.balances['stu'], b1 - 100_000)
#
#        self.elect_masternodes.unregister(signer='stu')
#
#        self.assertEqual(self.currency.balances['stu'], b1)

# N/A ?
#    def test_unregister_if_in_masternodes_throws_assert(self):
#        self.currency.approve(signer='stu', amount=100_000, to='elect_masternodes')
#        self.elect_masternodes.register(signer='stu')
#
#        with self.assertRaises(AssertionError):
#            self.elect_masternodes.unregister()

    def test_unregister_if_not_registered_throws_assert(self):
        with self.assertRaises(AssertionError):
            self.elect_masternodes.unregister()

    def test_vote_for_someone_not_registered_throws_assertion_error(self):
        with self.assertRaises(AssertionError):
            self.elect_masternodes.vote_candidate(address='stu')

    def test_vote_for_someone_registered_deducts_tau_and_adds_vote(self):
        # Give joe money
        self.currency.transfer(signer='stu', amount=100_000, to='joe')

        # Joe Allows Spending
        self.currency.approve(signer='joe', amount=100_000, to='elect_masternodes')

        self.elect_masternodes.register(signer='joe')

        self.currency.approve(signer='stu', amount=10_000, to='elect_masternodes')

        env = {'now': Datetime._from_datetime(dt.today())}

        stu_bal = self.currency.balances['stu']

        self.elect_masternodes.vote_candidate(signer='stu', address='joe', environment=env)

        self.assertEqual(self.currency.balances['stu'], stu_bal - 1)
        self.assertEqual(self.elect_masternodes.candidate_state['votes', 'joe'], 1)
        self.assertEqual(self.currency.balances['blackhole'], 1)
        self.assertEqual(self.elect_masternodes.candidate_state['last_voted', 'stu'], env['now'])

    def test_voting_again_too_soon_throws_assertion_error(self):
        # Give joe money
        self.currency.transfer(signer='stu', amount=100_000, to='joe')

        # Joe Allows Spending
        self.currency.approve(signer='joe', amount=100_000, to='elect_masternodes')

        self.elect_masternodes.register(signer='joe')

        self.currency.approve(signer='stu', amount=10_000, to='elect_masternodes')

        env = {'now': Datetime._from_datetime(dt.today())}

        self.elect_masternodes.vote_candidate(signer='stu', address='joe', environment=env)

        with self.assertRaises(AssertionError):
            self.elect_masternodes.vote_candidate(signer='stu', address='joe', environment=env)

    def test_voting_again_after_waiting_one_day_works(self):
        # Give joe money
        self.currency.transfer(signer='stu', amount=100_000, to='joe')

        # Joe Allows Spending
        self.currency.approve(signer='joe', amount=100_000, to='elect_masternodes')

        self.elect_masternodes.register(signer='joe')

        self.currency.approve(signer='stu', amount=10_000, to='elect_masternodes')

        stu_bal = self.currency.balances['stu']

        env = {'now': Datetime._from_datetime(dt.today())}

        self.elect_masternodes.vote_candidate(signer='stu', address='joe', environment=env)

        env = {'now': Datetime._from_datetime(dt.today() + td(days=7))}

        self.elect_masternodes.vote_candidate(signer='stu', address='joe', environment=env)

        self.assertEqual(self.currency.balances['stu'], stu_bal - 2)
        self.assertEqual(self.elect_masternodes.candidate_state['votes', 'joe'], 2)

        self.assertEqual(self.currency.balances['blackhole'], 2)

        self.assertEqual(self.elect_masternodes.candidate_state['last_voted', 'stu'], env['now'])

    def test_top_masternode_returns_none_if_no_candidates(self):
        self.assertIsNone(self.elect_masternodes.top_member())

    def test_top_masternode_returns_joe_if_registered_but_no_votes(self):
        self.currency.transfer(signer='stu', amount=100_000, to='joe')  # Give joe money
        self.currency.approve(signer='joe', amount=100_000, to='elect_masternodes')  # Joe Allows Spending
        self.elect_masternodes.register(signer='joe')  # Register Joe

        self.assertEqual(self.elect_masternodes.top_member(), 'joe')  # Joe is the current top spot

    def test_top_masternode_returns_bob_if_joe_and_bob_registered_but_bob_has_votes(self):
        self.currency.transfer(signer='stu', amount=100_000, to='joe')  # Give joe money
        self.currency.approve(signer='joe', amount=100_000, to='elect_masternodes')  # Joe Allows Spending
        self.elect_masternodes.register(signer='joe')  # Register Joe

        self.currency.transfer(signer='stu', amount=100_000, to='bob')  # Give Bob money
        self.currency.approve(signer='bob', amount=100_000, to='elect_masternodes')  # Bob Allows Spending
        self.elect_masternodes.register(signer='bob')  # Register Bob

        self.currency.approve(signer='stu', amount=10_000, to='elect_masternodes')  # Stu approves spending to vote
        env = {'now': Datetime._from_datetime(dt.today())}
        self.elect_masternodes.vote_candidate(signer='stu', address='bob', environment=env)  # Stu votes for Bob

        self.assertEqual(self.elect_masternodes.top_member(), 'bob')  # bob is the current top spot

    def test_top_masternode_returns_joe_if_joe_and_bob_registered_but_joe_first_and_no_votes(self):
        self.currency.transfer(signer='stu', amount=100_000, to='joe')  # Give joe money
        self.currency.approve(signer='joe', amount=100_000, to='elect_masternodes')  # Joe Allows Spending
        self.elect_masternodes.register(signer='joe')  # Register Joe

        self.currency.transfer(signer='stu', amount=100_000, to='bob')  # Give Bob money
        self.currency.approve(signer='bob', amount=100_000, to='elect_masternodes')  # Bob Allows Spending
        self.elect_masternodes.register(signer='bob')  # Register Bob

        self.assertEqual(self.elect_masternodes.top_member(), 'joe')  # Joe is the current top spot

    def test_pop_top_fails_if_not_masternodes_contract(self):
        with self.assertRaises(AssertionError):
            self.elect_masternodes.pop_top()

    def test_pop_top_doesnt_fail_if_masternode_contract(self):
        self.elect_masternodes.pop_top(signer='masternodes')

    def test_pop_top_deletes_bob_if_pop_is_top_masternode(self):
        self.currency.transfer(signer='stu', amount=100_000, to='joe')  # Give joe money
        self.currency.approve(signer='joe', amount=100_000, to='elect_masternodes')  # Joe Allows Spending
        self.elect_masternodes.register(signer='joe')  # Register Joe

        self.currency.transfer(signer='stu', amount=100_000, to='bob')  # Give Bob money
        self.currency.approve(signer='bob', amount=100_000, to='elect_masternodes')  # Bob Allows Spending
        self.elect_masternodes.register(signer='bob')  # Register Bob

        self.currency.approve(signer='stu', amount=10_000, to='elect_masternodes')  # Stu approves spending to vote
        env = {'now': Datetime._from_datetime(dt.today())}
        self.elect_masternodes.vote_candidate(signer='stu', address='bob', environment=env)  # Stu votes for Bob

        self.assertEqual(self.elect_masternodes.top_member(), 'bob')  # bob is the current top spot

        self.assertIsNotNone(self.elect_masternodes.candidate_state['votes', 'bob'])

        self.elect_masternodes.pop_top(signer='masternodes')

        self.assertIsNone(self.elect_masternodes.candidate_state['votes', 'bob'])

    def test_pop_top_returns_none_if_noone_registered(self):
        self.assertIsNone(self.elect_masternodes.pop_top(signer='masternodes'))

    def test_voting_no_confidence_against_non_committee_member_fails(self):
        with self.assertRaises(AssertionError):
            self.elect_masternodes.vote_no_confidence(address='whoknows')

    def test_vote_no_confidence_for_someone_registered_deducts_tau_and_adds_vote(self):
        self.currency.approve(signer='stu', amount=10_000, to='elect_masternodes')

        stu_bal = self.currency.balances['stu']

        env = {'now': Datetime._from_datetime(dt.today())}

        self.elect_masternodes.vote_no_confidence(signer='stu', address='raghu', environment=env) # Raghu is seeded in contract

        self.assertEqual(self.currency.balances['stu'], stu_bal - 1)
        self.assertEqual(self.elect_masternodes.no_confidence_state['votes', 'raghu'], 1)
        self.assertEqual(self.currency.balances['blackhole'], 1)
        self.assertEqual(self.elect_masternodes.no_confidence_state['last_voted', 'stu'], env['now'])

    def test_voting_no_confidence_again_too_soon_throws_assertion_error(self):
        self.currency.approve(signer='stu', amount=10_000, to='elect_masternodes')

        env = {'now': Datetime._from_datetime(dt.today())}

        self.elect_masternodes.vote_no_confidence(signer='stu', address='raghu', environment=env)

        with self.assertRaises(AssertionError):
            self.elect_masternodes.vote_no_confidence(signer='stu', address='raghu', environment=env)

    def test_voting_no_confidence_again_after_waiting_one_day_works(self):
        self.currency.approve(signer='stu', amount=10_000, to='elect_masternodes')

        stu_bal = self.currency.balances['stu']

        env = {'now': Datetime._from_datetime(dt.today())}

        self.elect_masternodes.vote_no_confidence(signer='stu', address='raghu', environment=env)

        env = {'now': Datetime._from_datetime(dt.today() + td(days=7))}

        self.elect_masternodes.vote_no_confidence(signer='stu', address='raghu', environment=env)

        self.assertEqual(self.currency.balances['stu'], stu_bal - 2)
        self.assertEqual(self.elect_masternodes.no_confidence_state['votes', 'raghu'], 2)

        self.assertEqual(self.currency.balances['blackhole'], 2)

        self.assertEqual(self.elect_masternodes.no_confidence_state['last_voted', 'stu'], env['now'])

    def test_last_masternode_returns_none_if_no_candidates(self):
        self.assertIsNone(self.elect_masternodes.last_member())

    def test_last_masternode_returns_none_if_no_votes(self):
        self.assertEqual(self.elect_masternodes.last_member(), None)  # Joe is the current top spot

    def test_relinquish_fails_if_not_in_masternodes(self):
        with self.assertRaises(AssertionError):
            self.elect_masternodes.relinquish(signer='joebob')

    def test_relinquish_adds_ctx_signer_if_in_masternodes(self):
        self.elect_masternodes.relinquish(signer='raghu')

        self.assertEqual('raghu', self.elect_masternodes.to_be_relinquished.get())

    def test_last_masternode_returns_relinquished_if_there_is_one_to_be_relinquished(self):
        self.elect_masternodes.relinquish(signer='raghu')

        self.assertEqual(self.elect_masternodes.last_member(), 'raghu')

    def test_error_if_someone_tries_to_relinquish_when_another_exists(self):
        self.elect_masternodes.relinquish(signer='raghu')
        with self.assertRaises(AssertionError):
            self.elect_masternodes.relinquish(signer='stux')

    def test_last_masternode_returns_masternode_with_most_votes_if_none_in_relinquished(self):
        self.currency.approve(signer='stu', amount=10_000, to='elect_masternodes')  # Stu approves spending to vote
        env = {'now': Datetime._from_datetime(dt.today())}
        self.elect_masternodes.vote_no_confidence(signer='stu', address='raghu', environment=env)  # Stu votes for Bob

        self.assertEqual(self.elect_masternodes.last_member(), 'raghu')  # bob is the current top spot

    def test_last_masternode_returns_first_in_if_tie(self):
        self.currency.approve(signer='stu', amount=10_000, to='elect_masternodes')

        env = {'now': Datetime._from_datetime(dt.today())}

        self.elect_masternodes.vote_no_confidence(signer='stu', address='stux', environment=env)

        env = {'now': Datetime._from_datetime(dt.today() + td(days=7))}

        self.elect_masternodes.vote_no_confidence(signer='stu', address='raghu', environment=env)

        self.assertEqual(self.elect_masternodes.last_member(), 'stux')

    def test_last_masternode_returns_least_popular_if_multiple_votes(self):
        self.currency.approve(signer='stu', amount=10_000, to='elect_masternodes')

        env = {'now': Datetime._from_datetime(dt.today())}
        self.elect_masternodes.vote_no_confidence(signer='stu', address='stux', environment=env)

        env = {'now': Datetime._from_datetime(dt.today() + td(days=7))}
        self.elect_masternodes.vote_no_confidence(signer='stu', address='raghu', environment=env)

        env = {'now': Datetime._from_datetime(dt.today() + td(days=14))}
        self.elect_masternodes.vote_no_confidence(signer='stu', address='stux', environment=env)

        self.assertEqual(self.elect_masternodes.last_member(), 'stux')

    def test_pop_last_fails_if_not_masternodes_contract(self):
        with self.assertRaises(AssertionError):
            self.elect_masternodes.pop_last()

    def test_pop_last_doesnt_fail_if_masternodes_contract(self):
        self.elect_masternodes.pop_last(signer='masternodes')

    def test_pop_last_deletes_stux_if_is_last_masternode_and_no_relinquished(self):
        self.currency.approve(signer='stu', amount=10_000, to='elect_masternodes')

        env = {'now': Datetime._from_datetime(dt.today())}
        self.elect_masternodes.vote_no_confidence(signer='stu', address='stux', environment=env)

        self.assertIsNotNone(self.elect_masternodes.no_confidence_state['votes', 'stux'])
        self.elect_masternodes.pop_last(signer='masternodes')
        self.assertIsNone(self.elect_masternodes.no_confidence_state['votes', 'stux'])

    def test_pop_last_deletes_raghu_if_stux_voted_but_raghu_relinquished(self):
        self.currency.approve(signer='stu', amount=10_000, to='elect_masternodes')

        env = {'now': Datetime._from_datetime(dt.today())}
        self.elect_masternodes.vote_no_confidence(signer='stu', address='stux', environment=env)

        self.elect_masternodes.relinquish(signer='raghu')

        self.assertIsNotNone(self.elect_masternodes.no_confidence_state['votes', 'stux'])
        self.assertIn('raghu', self.elect_masternodes.to_be_relinquished.get())

        self.elect_masternodes.pop_last(signer='masternodes')

        self.assertIsNotNone(self.elect_masternodes.no_confidence_state['votes', 'stux'])

    def test_pop_last_deletes_raghu_from_no_confidence_hash_if_relinquished(self):
        self.currency.approve(signer='stu', amount=10_000, to='elect_masternodes')

        env = {'now': Datetime._from_datetime(dt.today())}
        self.elect_masternodes.vote_no_confidence(signer='stu', address='raghu', environment=env)

        self.elect_masternodes.relinquish(signer='raghu')

        self.assertIsNotNone(self.elect_masternodes.no_confidence_state['votes', 'raghu'])
        self.assertIn('raghu', self.elect_masternodes.to_be_relinquished.get())

        self.elect_masternodes.pop_last(signer='masternodes')

        self.assertEqual(self.elect_masternodes.no_confidence_state['votes', 'raghu'], 0)

    def test_no_confidence_pop_last_prevents_unregistering(self):
        # Give Raghu money
        self.currency.transfer(signer='stu', amount=100_000, to='raghu')

        # Raghu Allows Spending
        self.currency.approve(signer='raghu', amount=100_000, to='elect_masternodes')

        self.elect_masternodes.register(signer='raghu')

        self.currency.approve(signer='stu', amount=10_000, to='elect_masternodes')

        self.elect_masternodes.vote_no_confidence(signer='stu', address='raghu')

        self.elect_masternodes.pop_last(signer='masternodes')

        self.assertFalse(self.elect_masternodes.candidate_state['registered', 'raghu'])

        with self.assertRaises(AssertionError):
            self.elect_masternodes.unregister(signer='raghu')

    def test_relinquish_pop_last_allows_unregistering(self):
        # Give Raghu money
        self.currency.transfer(signer='stu', amount=100_000, to='raghu')

        # Raghu Allows Spending
        self.currency.approve(signer='raghu', amount=100_000, to='elect_masternodes')

        self.elect_masternodes.register(signer='raghu')

        self.currency.approve(signer='stu', amount=10_000, to='elect_masternodes')

        self.elect_masternodes.vote_no_confidence(signer='stu', address='raghu')
        self.elect_masternodes.relinquish(signer='raghu')
        self.elect_masternodes.pop_last(signer='masternodes')

        self.assertTrue(self.elect_masternodes.candidate_state['registered', 'raghu'])
        self.masternodes.quick_write('S', 'members', ['stu'])
        self.elect_masternodes.unregister(signer='raghu')

    def test_force_removal_fails_if_not_masternodes(self):
        with self.assertRaises(AssertionError):
            self.elect_masternodes.force_removal(address='stux')

    def test_force_removal_unregisters_address(self):
        # Give Raghu money
        self.currency.transfer(signer='stu', amount=100_000, to='stux')

        # Raghu Allows Spending
        self.currency.approve(signer='stux', amount=100_000, to='elect_masternodes')

        self.elect_masternodes.register(signer='stux')
        self.elect_masternodes.force_removal(signer='masternodes', address='stux')
        self.assertFalse(self.elect_masternodes.candidate_state['registered', 'stux'])