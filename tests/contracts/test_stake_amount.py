import unittest
from unittest import TestCase
from cilantro.logger import get_logger
from tests.contracts.smart_contract_testcase import *
from seneca.execute import execute_contract
import seneca.libs.types as std
import time

log = get_logger("TestElection")
user_id = 'tester'

class TestElection(SmartContractTestCase):

    @contract(
        ('a', 'witness_stake_amount'),
        ('b', 'witness_stake_amount'),
        ('c', 'witness_stake_amount')
    )
    def test_stake_amount(self,a,b,c):
        election_id = a.create_election(std.timedelta(seconds=30))
        a.cast_vote(election_id, 10000)
        b.cast_vote(election_id, 10000)
        c.cast_vote(election_id, 12000)
        res = a.tally_votes(election_id)
        self.assertEqual(res, 10000)
        self.assertEqual(a.get(), 10000)

    #TODO include when upsert implemented
    # @contract(
    #     ('a', 'witness_stake_amount'),
    #     ('b', 'witness_stake_amount'),
    #     ('c', 'witness_stake_amount')
    # )
    # def test_update_vote(self,a,b,c):
    #     election_id = a.create_election(std.timedelta(seconds=30))
    #     a.cast_vote(election_id, 10000)
    #     a.cast_vote(election_id, 12000)
    #     b.cast_vote(election_id, 10000)
    #     c.cast_vote(election_id, 12000)
    #     res = a.tally_votes(election_id)
    #     self.assertEqual(res, 12000)

if __name__ == '__main__':
    unittest.main()
