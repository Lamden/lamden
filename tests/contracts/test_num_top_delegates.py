import unittest
from unittest import TestCase
from cilantro.logger import get_logger
from tests.contracts.smart_contract_testcase import *
from seneca.execute_sc import execute_contract


log = get_logger("Testelection")

class TestNumTopDelegates(SmartContractTestCase):
    @contract('num_top_delegates')
    def test_voting_process(self, election):
        election_id = election.start_election('{policy_maker}')
        election.cast_vote('voter_1', election_id, 5)
        election.cast_vote('voter_2', election_id, 5)
        election.cast_vote('voter_3', election_id, 7)
        res = election.tally_votes('policy_maker', election_id)

if __name__ == '__main__':
    unittest.main()
