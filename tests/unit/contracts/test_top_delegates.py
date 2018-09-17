import unittest
from unittest import TestCase
from cilantro.logger import get_logger
import seneca.libs.types as std
from tests.unit.contracts.smart_contract_testcase import *
from seneca.execute import execute_contract


log = get_logger("Testelection")

class TestTopDelegates(SmartContractTestCase):
    @contract(
        ('a', 'num_top_delegates'),
        ('b', 'num_top_delegates'),
        ('c', 'num_top_delegates'),
        ('a', 'top_delegates'),
        ('b', 'top_delegates'),
        ('c', 'top_delegates'),
    )
    def test_voting_process(self, a1, b1, c1, a2, b2, c2):
        election_id = a1.create_election(std.timedelta(seconds=30))
        a1.cast_vote(election_id, 2)
        b1.cast_vote(election_id, 2)
        c1.cast_vote(election_id, 3)
        res = a1.tally_votes(election_id)

        election_id = a2.create_election(std.timedelta(seconds=30))
        a2.cast_vote(election_id, ['a'])
        b2.cast_vote(election_id, ['a','b'])
        c2.cast_vote(election_id, ['c'])
        res = a2.tally_votes(election_id)
        self.assertEqual(res[0], 'a')

if __name__ == '__main__':
    unittest.main()
