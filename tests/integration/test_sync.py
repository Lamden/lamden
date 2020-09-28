from unittest import TestCase
from . import mock
import os
from lamden.contracts import sync
from contracting.db.driver import ContractDriver, Driver
from contracting.client import ContractingClient


MOCK_ROOT = os.path.dirname(os.path.abspath(mock.__file__))
MOCK_GENESIS = MOCK_ROOT + '/genesis.json'
MOCK_SUBMISSION = MOCK_ROOT + '/submission.s.py'


class TestSync(TestCase):
    def setUp(self):
        self.client = ContractingClient()
        self.client.flush()

    def tearDown(self):
        self.client.flush()

    def test_delete(self):
        sync.submit_from_genesis_json_file(
            client=self.client
        )

        submission_code_1 = self.client.raw_driver.get('submission.__code__')

        sync.flush_sys_contracts(client=self.client, filename=MOCK_GENESIS, submission_path=MOCK_SUBMISSION)

        sync.submit_from_genesis_json_file(
            client=self.client,
            filename=MOCK_GENESIS,
            root=MOCK_ROOT
        )

        submission_code_2 = self.client.raw_driver.get('submission.__code__')

        self.assertNotEqual(submission_code_1, submission_code_2)
