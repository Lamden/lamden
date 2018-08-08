import unittest
from unittest import TestCase
from unittest.mock import patch, Mock
from cilantro.logger import get_logger
from tests.contracts.smart_contract_testcase import *
from seneca.execute import execute_contract
import seneca.libs.types as std
import time, datetime

log = get_logger("TestElection")
user_id = 'tester'
call_count = 0

class TestElection(SmartContractTestCase):
    @contract(
        ('a', 'witness_stake_amount'),
        ('b', 'witness_stake_amount'),
        ('c', 'witness_stake_amount'),
        ('DAVIS', 'witness'),
        ('DAVIS', 'currency')
    )
    def test_stake(self, a,b,c,davis, davis_currency):
        election_id = a.create_election(std.timedelta(seconds=30))
        a.cast_vote(election_id, 10000)
        b.cast_vote(election_id, 10000)
        c.cast_vote(election_id, 12000)
        res = a.tally_votes(election_id)
        self.assertEqual(davis_currency.get_balance(), 3696947)
        davis.stake()
        self.assertTrue(davis.is_witness())
        self.assertEqual(davis_currency.get_balance(), 3686947)

    # TODO seneca is not currently mockable
    # @contract(
    #     ('a', 'witness_stake_amount'),
    #     ('b', 'witness_stake_amount'),
    #     ('c', 'witness_stake_amount'),
    #     ('DAVIS', 'witness'),
    #     ('DAVIS', 'currency')
    # )
    # def test_unstake(self, a,b,c,davis, davis_currency):
    #     now = std.datetime.now()
    #     with mock_datetime(now, std):
    #         election_id = a.create_election(std.timedelta(seconds=1))
    #         a.cast_vote(election_id, 10000)
    #         b.cast_vote(election_id, 10000)
    #         c.cast_vote(election_id, 12000)
    #         res = a.tally_votes(election_id)
    #         davis.stake()
    #     with mock_datetime(now+std.timedelta(days=31), std):
    #         davis.unstake()

    @contract(
        ('a', 'witness_stake_amount'),
        ('b', 'witness_stake_amount'),
        ('c', 'witness_stake_amount'),
        ('DAVIS', 'witness')
    )
    def test_unstake_fail(self, a,b,c,davis):
        election_id = a.create_election(std.timedelta(seconds=30))
        a.cast_vote(election_id, 10000)
        b.cast_vote(election_id, 10000)
        c.cast_vote(election_id, 12000)
        res = a.tally_votes(election_id)
        davis.stake()
        with self.assertRaises(Exception) as context:
            davis.unstake()

    @contract(
        ('a', 'witness_stake_amount'),
        ('b', 'witness_stake_amount'),
        ('c', 'witness_stake_amount'),
        ('DAVIS', 'witness'),
        ('CARL', 'witness')
    )
    def test_is_witness(self, a,b,c, davis,carl):
        election_id = a.create_election(std.timedelta(seconds=30))
        a.cast_vote(election_id, 10000)
        b.cast_vote(election_id, 10000)
        c.cast_vote(election_id, 12000)
        res = a.tally_votes(election_id)
        davis.stake()
        self.assertTrue(carl.is_witness('DAVIS'))

    @contract(
        ('a', 'witness_stake_amount'),
        ('b', 'witness_stake_amount'),
        ('c', 'witness_stake_amount'),
        ('CARL', 'witness')
    )
    def test_is_witness_fail(self, a,b,c, carl):
        election_id = a.create_election(std.timedelta(seconds=30))
        a.cast_vote(election_id, 10000)
        b.cast_vote(election_id, 10000)
        c.cast_vote(election_id, 12000)
        res = a.tally_votes(election_id)
        self.assertFalse(carl.is_witness('DAVIS'))

    @contract(
        ('a', 'witness_stake_amount'),
        ('b', 'witness_stake_amount'),
        ('c', 'witness_stake_amount'),
        ('DAVIS', 'witness'),
        ('CARL', 'witness')
    )
    def test_get_vks(self, a,b,c, davis, carl):
        election_id = a.create_election(std.timedelta(seconds=30))
        a.cast_vote(election_id, 10000)
        b.cast_vote(election_id, 10000)
        c.cast_vote(election_id, 12000)
        res = a.tally_votes(election_id)
        davis.stake()
        carl.stake()
        self.assertEqual(
            list(carl.get_vks()),
            [{'id': 2, 'witness_id': 'CARL'}, {'id': 1, 'witness_id': 'DAVIS'}]
        )


if __name__ == '__main__':
    unittest.main()
