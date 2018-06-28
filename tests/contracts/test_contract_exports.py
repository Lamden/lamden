import unittest
from unittest import TestCase
from cilantro.logger import get_logger
from tests.contracts.smart_contract_testcase import SmartContractTestCase, contract
from seneca.execute_sc import execute_contract

log = get_logger("Testelection")

voter_1 = 'voter_1'
voter_2 = 'voter_2'
voter_3 = 'voter_3'
policy_maker = 'policy_maker'

class TestContractExports(SmartContractTestCase):

    @contract('num_top_delegates')
    def test_exports(self, sc):
        election_id = sc.start_election(policy_maker)
        sc.cast_vote(voter_1, election_id, 5)
        sc.cast_vote(voter_2, election_id, 5)
        sc.cast_vote(voter_3, election_id, 7)
        res = sc.tally_votes(policy_maker, election_id)
        self.assertEqual(res, 5)

if __name__ == '__main__':
    unittest.main()
