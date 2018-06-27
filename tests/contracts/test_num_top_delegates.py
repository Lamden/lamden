import unittest
from unittest import TestCase
from cilantro.logger import get_logger
from tests.contracts.smart_contract_testcase import SamrtContractTestCase
from seneca.execute_sc import execute_contract


log = get_logger("Testelection")

voter_1 = 'voter_1'
voter_2 = 'voter_2'
voter_3 = 'voter_3'
policy_maker = 'policy_maker'

class TestNumTopDelegates(SamrtContractTestCase):
    def test_voting_process(self):
        self.run_contract(code_str="""
import num_top_delegates as election

election_id = election.start_election('{policy_maker}')
election.cast_vote('{voter_1}', election_id, 5)
election.cast_vote('{voter_2}', election_id, 5)
election.cast_vote('{voter_3}', election_id, 7)
res = election.tally_votes('{policy_maker}', election_id)
print('>>> voting result is:', res,'<<<')

        """.format(policy_maker=policy_maker,
            voter_1=voter_1,
            voter_2=voter_2,
            voter_3=voter_3)
        )

if __name__ == '__main__':
    unittest.main()
