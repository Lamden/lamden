from contracting.client import ContractingClient
from contracting.db.driver import ContractDriver, FSDriver
from contracting.stdlib.bridge.time import Datetime
from datetime import datetime as dt, timedelta as td
from lamden.contracts import sync
from pathlib import Path
from unittest import TestCase

class TestStamps(TestCase):
    def setUp(self):
        self.contract_driver = ContractDriver(driver=FSDriver(root=Path('/tmp/temp_filebased_state')))
        self.client = ContractingClient(driver=self.contract_driver)
        self.client.flush()

        with open(sync.DEFAULT_PATH + '/genesis/election_house.s.py') as f:
            contract = f.read()

        self.client.submit(contract, name='election_house')

        with open(sync.DEFAULT_PATH + '/genesis/stamp_cost.s.py') as f:
            contract = f.read()

        self.client.submit(contract, name='stamp_cost')

        with open(sync.DEFAULT_PATH + '/genesis/members.s.py') as f:
            contract = f.read()

        self.client.submit(contract, name='masternodes', owner='election_house', constructor_args={
            'initial_members': ['a', 'b', 'c', 'd', 'e', 'f'],
            'candidate': 'elect_masters'
        })

        self.election_house = self.client.get_contract('election_house')
        self.election_house.register_policy(contract='masternodes')

        self.stamp_cost = self.client.get_contract('stamp_cost')

    def test_initial_value(self):
        self.assertEqual(self.stamp_cost.current_value(), 100)

    def test_validate_vote_fails_if_not_node(self):
        with self.assertRaises(AssertionError):
            self.stamp_cost.run_private_function(
                f='validate_vote',
                signer='stu',
                vk='stu',
                obj=120
            )

    def test_validate_vote_fails_if_not_int(self):
        with self.assertRaises(AssertionError):
            self.stamp_cost.run_private_function(
                f='validate_vote',
                signer='stu',
                vk='a',
                obj=123038.125125
            )

    def test_validate_vote_fails_if_negative(self):
        with self.assertRaises(AssertionError):
            self.stamp_cost.run_private_function(
                f='validate_vote',
                signer='stu',
                vk='a',
                obj=-120
            )

    def test_validate_vote_fails_if_too_large(self):
        with self.assertRaises(AssertionError):
            self.stamp_cost.run_private_function(
                f='validate_vote',
                signer='stu',
                vk='a',
                obj=250
            )

    def test_validate_vote_fails_if_too_small(self):
        with self.assertRaises(AssertionError):
            self.stamp_cost.run_private_function(
                f='validate_vote',
                signer='stu',
                vk='a',
                obj=25
            )

    def test_validate_vote_if_already_voted(self):
        self.stamp_cost.quick_write(variable='S', args=['votes', 'a'], value=True)

        with self.assertRaises(AssertionError):
            self.stamp_cost.run_private_function(
                f='validate_vote',
                signer='stu',
                vk='a',
                obj=100
            )

    def test_validate_passes_if_all_good(self):
        self.stamp_cost.run_private_function(
            f='validate_vote',
            signer='stu',
            vk='a',
            obj=120
        )

    def test_tally_vote_adds_to_current_total(self):
        self.assertEqual(self.stamp_cost.quick_read('S', 'current_total'), 100)

        self.stamp_cost.run_private_function(
            f='tally_vote',
            signer='stu',
            vk='a',
            obj=120
        )

        self.assertEqual(self.stamp_cost.quick_read('S', 'current_total'), 220)

    def test_tally_vote_adds_to_vote_count(self):
        self.assertEqual(self.stamp_cost.quick_read('S', 'vote_count'), 1)

        self.stamp_cost.run_private_function(
            f='tally_vote',
            signer='stu',
            vk='a',
            obj=120
        )

        self.assertEqual(self.stamp_cost.quick_read('S', 'vote_count'), 2)

    def test_tally_vote_sets_to_has_voted(self):
        self.assertEqual(self.stamp_cost.quick_read('S', 'has_voted', ['a']), None)

        self.stamp_cost.run_private_function(
            f='tally_vote',
            signer='stu',
            vk='a',
            obj=120
        )

        self.assertEqual(self.stamp_cost.quick_read('S', 'has_voted', ['a']), True)

    def test_election_is_over_if_more_than_max_time_past_first_vote(self):
        self.stamp_cost.vote(vk='a', obj=120)

        env = {'now': Datetime._from_datetime(dt.today() + td(days=7))}

        res = self.stamp_cost.run_private_function(
            f='election_is_over',
            signer='stu',
            environment=env
        )

        self.assertTrue(res)

    def test_election_over_if_more_than_min_required_vote(self):
        self.stamp_cost.vote(vk='a', obj=120)
        self.stamp_cost.vote(vk='b', obj=120)
        self.stamp_cost.vote(vk='c', obj=120)
        self.stamp_cost.vote(vk='d', obj=120)

        env = {'now': Datetime._from_datetime(dt.today() + td(days=7))}

        res = self.stamp_cost.run_private_function(
            f='election_is_over',
            signer='stu',
            environment=env
        )

        self.assertTrue(res)

    def test_second_vote_simply_tallies_vote(self):
        self.stamp_cost.vote(vk='a', obj=120)
        self.stamp_cost.vote(vk='b', obj=130)

        self.assertEqual(self.stamp_cost.S['current_total'], 350)

    def test_complete_election_updates_value(self):
        self.stamp_cost.vote(vk='a', obj=120)
        self.stamp_cost.vote(vk='b', obj=55)
        self.stamp_cost.vote(vk='c', obj=65)
        self.stamp_cost.vote(vk='d', obj=200)

        self.assertIsNone(self.stamp_cost.S['election_start'])

        self.assertEqual(self.stamp_cost.current_value(), 108)