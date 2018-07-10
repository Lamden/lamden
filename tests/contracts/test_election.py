import unittest
from unittest import TestCase
from cilantro.logger import get_logger
from tests.contracts.smart_contract_testcase import *
from seneca.execute_sc import execute_contract
import seneca.smart_contract_user_libs.stdlib as std
import time

log = get_logger("TestElection")
user_id = 'tester'

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
        election_id = election.create_election(std.timedelta(seconds=1), int)
        self.assertEqual(election_id, 1)

    @contract('election')
    def test_create_fail(self, election):
        with self.assertRaises(Exception) as context:
            election_id = election.create_election(123, int)

    @contract('election')
    def test_get_election(self, election):
        election_id = election.create_election(std.timedelta(seconds=37), int)
        e = election.get_election(election_id)
        self.assertEqual(e['opened_ts'], e['expire_on']-std.timedelta(seconds=37))

    # TODO wait until Seneca support time comparison
    # @contract('election')
    # def test_get_election_failed(self, election):
    #     election_id = election.create_election(std.timedelta(seconds=1), int)
    #     time.sleep(1.5)
    #     e = election.get_active_election(election_id, if_active=True)

    @contract('election')
    def test_pass(self, election):
        election_id = election.create_election(std.timedelta(seconds=10), int)
        election.pass_election(election_id)

    @contract('election')
    def test_fail(self, election):
        election_id = election.create_election(std.timedelta(seconds=10), int)
        election.fail_election(election_id)

    @contract('election')
    def test_cancel(self, election):
        election_id = election.create_election(std.timedelta(seconds=10), int)
        election.cancel_election(election_id)

if __name__ == '__main__':
    unittest.main()
