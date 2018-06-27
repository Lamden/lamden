import unittest
from unittest import TestCase
from cilantro.logger import get_logger
from tests.contracts.smart_contract_testcase import SamrtContractTestCase
from seneca.execute_sc import execute_contract


log = get_logger("TestBallot")

voter_1 = 'voter_1'
voter_2 = 'voter_2'
voter_3 = 'voter_3'
policy_maker = 'policy_maker'

class TestTopDelegates(SamrtContractTestCase):
    def test_voting_process(self):
        self.run_contract(code_str="""

import num_top_delegates as ntd

ballot_id = ntd.start_ballot('{policy_maker}')
ntd.cast_vote('{voter_1}', ballot_id, 2)
ntd.cast_vote('{voter_2}', ballot_id, 2)
ntd.cast_vote('{voter_3}', ballot_id, 3)
res = ntd.tally_votes('{policy_maker}', ballot_id)

import top_delegates as td

ballot_id = td.start_ballot('{policy_maker}')
td.cast_vote('{voter_1}', ballot_id, ['{voter_1}'])
td.cast_vote('{voter_1}', ballot_id, ['{voter_1}'])
td.cast_vote('{voter_2}', ballot_id, ['{voter_1}','{voter_2}'])
td.cast_vote('{voter_3}', ballot_id, ['{voter_3}'])
res = td.tally_votes('{policy_maker}', ballot_id)
print('>>> voting result is:', res,'<<<')

        """.format(policy_maker=policy_maker,
            voter_1=voter_1,
            voter_2=voter_2,
            voter_3=voter_3)
        )

if __name__ == '__main__':
    unittest.main()
