import unittest
from unittest import TestCase
from cilantro.logger import get_logger
from tests.contracts.smart_contract_testcase import *
from seneca.execute_sc import execute_contract


log = get_logger("Testelection")

class TestTopDelegates(SmartContractTestCase):

    @contract('num_top_delegates', 'top_delegates')
    def test_voting_process(self, ntd, td):

        election_id = ntd.start_election('policy_maker')
        ntd.cast_vote('voter_1', election_id, 2)
        ntd.cast_vote('voter_2', election_id, 2)
        ntd.cast_vote('voter_3', election_id, 3)
        res = ntd.tally_votes('{policy_maker}', election_id)

        election_id = td.start_election('policy_maker')
        td.cast_vote('voter_1', election_id, ['voter_1'])
        td.cast_vote('voter_1', election_id, ['voter_1'])
        td.cast_vote('voter_2', election_id, ['voter_1','voter_2'])
        td.cast_vote('voter_3', election_id, ['voter_3'])
        res = td.tally_votes('policy_maker', election_id)
        self.assertEqual(res[0], ('voter_1', 2))

if __name__ == '__main__':
    unittest.main()
