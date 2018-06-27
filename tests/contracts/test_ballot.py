import unittest
from unittest import TestCase
from cilantro.logger import get_logger
from tests.contracts.smart_contract_testcase import SamrtContractTestCase
from seneca.execute_sc import execute_contract


log = get_logger("Testelection")
user_id = 'tester'
POLICY = 'test_election'

class Testelection(SamrtContractTestCase):
    def test_enum(self):
        self.run_contract(code_str="""
import election
STATUS = election.enum()
assert STATUS.OPENED == 0
assert STATUS.PASSED == 1
assert STATUS.NOT_PASSED == 2
assert STATUS.CANCELLED == 3
        """.format(user_id, POLICY))
    def test_create(self):
        self.run_contract(code_str="""
import election
election_id = election.create_election('{user_id}', '{POLICY}', tags=['dogs', 'cats'])
assert election_id == 1, 'election not created!'
        """.format(user_id=user_id, POLICY=POLICY))
    def test_close(self):
        self.run_contract(code_str="""
import election
STATUS = election.enum()
election_id = election.create_election('{user_id}', '{POLICY}', tags=['dogs', 'cats'])
election.close_election('{user_id}', '{POLICY}', STATUS.PASSED)
        """.format(user_id=user_id, POLICY=POLICY))


if __name__ == '__main__':
    unittest.main()
