import unittest
from unittest import TestCase

from unittest.mock import patch
from cilantro.logger import get_logger
from tests.contracts.smart_contract_testcase import *
from seneca.execute_sc import execute_contract


log = get_logger("Testelection")

class TestWitness(SmartContractTestCase):

    @contract(
        ('a','stake'),
        ('b','stake'),
        ('c','stake'),
        ('DAVIS','witness'),
        'currency'
    )
    def test_staking(self, a_stake, b_stake, c_stake, witness, currency):
        election_id = a_stake.start_election('witness_stake')
        a_stake.cast_vote(election_id, 10000)
        b_stake.cast_vote(election_id, 10000)
        c_stake.cast_vote(election_id, 30000)
        a_stake.tally_votes(election_id)
        witness.stake()
        self.assertEqual(currency.get_balance('DAVIS'), 3686947)
        witness.unstake()
        self.assertEqual(currency.get_balance('DAVIS'), 3696947)

if __name__ == '__main__':
    unittest.main()
