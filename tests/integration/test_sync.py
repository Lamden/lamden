from unittest import TestCase
from . import mock
import os
from lamden.contracts import sync
from contracting.db.driver import ContractDriver, Driver
from contracting.client import ContractingClient
import glob
import json

from lamden.storage import StateManager

MOCK_ROOT = os.path.dirname(os.path.abspath(mock.__file__))
MOCK_GENESIS = MOCK_ROOT + '/genesis.json'
MOCK_SUBMISSION = MOCK_ROOT + '/submission.s.py'


class TestSync(TestCase):
    def setUp(self):
        self.client = ContractingClient()
        self.state = StateManager()
        self.state.flush()
        self.client.flush()

    def tearDown(self):
        self.client.flush()
        self.state.flush()

    def test_delete(self):
        sync.submit_from_genesis_json_file(
            client=self.client
        )

        submission_code_1 = self.client.raw_driver.get('submission.__code__')

        sync.flush_sys_contracts(client=self.client, filename=MOCK_GENESIS, submission_path=MOCK_SUBMISSION)

        sync.submit_from_genesis_json_file_2(
            state=self.state,
            filename=MOCK_GENESIS,
            root=MOCK_ROOT
        )

        submission_code_2 = self.client.raw_driver.get('submission.__code__')

        self.assertNotEqual(submission_code_1, submission_code_2)

    def test_all_code_is_there(self):
        with open(MOCK_GENESIS) as f:
            genesis = json.load(f)

        names = [g['name'] for g in genesis['contracts']]

        for name in names:
            self.assertIsNone(self.client.raw_driver.get(f'{name}.__code__'))

        sync.submit_from_genesis_json_file_2(
            state=self.state,
            filename=MOCK_GENESIS,
            root=MOCK_ROOT
        )

        for name in names:
            self.assertIsNotNone(self.client.raw_driver.get(f'{name}.__code__'))
