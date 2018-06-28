import unittest
from unittest import TestCase
from cilantro.logger import get_logger
from tests.contracts.smart_contract_testcase import *
from seneca.execute_sc import execute_contract

log = get_logger("TestElection")
user_id = 'tester'
POLICY = 'test_election'

class TestElection(SmartContractTestCase):
    @contract('election')
    def test_enum(self, election):
        STATUS = election.enum()
        self.assertEqual(STATUS.OPENED, 0)
        self.assertEqual(STATUS.PASSED, 1)
        self.assertEqual(STATUS.NOT_PASSED, 2)
        self.assertEqual(STATUS.CANCELLED, 3)

    @contract('election')
    def test_create(self, election):
        election_id = election.create_election(user_id, POLICY, tags=['dogs', 'cats'])
        self.assertEqual(election_id, 1)

    @contract('election')
    def test_close(self, election):
        STATUS = election.enum()
        election_id = election.create_election('{user_id}', '{POLICY}', tags=['dogs', 'cats'])
        election.close_election(user_id, POLICY, STATUS.PASSED)

if __name__ == '__main__':
    unittest.main()
