import unittest
from unittest import TestCase
from cilantro.logger import get_logger
from tests.contracts.smart_contract_testcase import SamrtContractTestCase
from seneca.execute_sc import execute_contract


log = get_logger("TestBallot")
user_id = 'tester'
POLICY = 'test_ballot'

class TestBallot(SamrtContractTestCase):
    def test_enum(self):
        self.run_contract(code_str="""
import ballot
STATUS = ballot.enum()
assert STATUS.OPENED == 0
assert STATUS.PASSED == 1
assert STATUS.NOT_PASSED == 2
assert STATUS.CANCELLED == 3
        """.format(user_id, POLICY))
    def test_create(self):
        self.run_contract(code_str="""
import ballot
ballot_id = ballot.create_ballot('{user_id}', '{POLICY}', tags=['dogs', 'cats'])
assert ballot_id == 1, 'Ballot not created!'
        """.format(user_id=user_id, POLICY=POLICY))
    def test_close(self):
        self.run_contract(code_str="""
import ballot
STATUS = ballot.enum()
ballot_id = ballot.create_ballot('{user_id}', '{POLICY}', tags=['dogs', 'cats'])
ballot.close_ballot('{user_id}', '{POLICY}', STATUS.PASSED)
        """.format(user_id=user_id, POLICY=POLICY))


if __name__ == '__main__':
    unittest.main()
