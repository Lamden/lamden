import unittest
from unittest import TestCase
from cilantro.logger import get_logger
from tests.contracts.smart_contract_testcase import *
import seneca.smart_contract_user_libs.stdlib as std
from seneca.execute_sc import execute_contract

log = get_logger("Testelection")

class TestNumTopDelegates(SmartContractTestCase):
    @contract(
        ('policy_maker', 'num_top_delegates'),
        ('voter_1', 'num_top_delegates'),
        ('voter_2', 'num_top_delegates'),
        ('voter_3', 'num_top_delegates'),
        'basic_math'
    )
    def test_voting_process(self, pm, v1, v2, v3, basic_math):
        election_id = pm.create_election(std.timedelta(seconds=30), int)
        v1.cast_vote(election_id, 5)
        v2.cast_vote(election_id, 5)
        v3.cast_vote(election_id, 7)
        res = v3.tally_votes(election_id)
        self.assertEqual(res, 5)


if __name__ == '__main__':
    unittest.main()
