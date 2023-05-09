
from unittest import TestCase
from lamden.cli import cmd

import os
import shutil

class TestCMD(TestCase):
    def setUp(self):
        self.test_dir = './.lamden'
        self.test_path = os.path.abspath(self.test_dir)
        self.create_directories()

    def tearDown(self):
        pass

    def create_directories(self):
        if os.path.exists(self.test_path):
            shutil.rmtree(self.test_path)

        os.makedirs(self.test_path)

    def test_FUNCTION_release_all_state_locks(self):

        state_path = os.path.join(self.test_path, 'contract_state')
        lock_dir = os.path.join(state_path, 'con_something-lock')

        os.makedirs(lock_dir)

        # assert lock exists
        self.assertTrue(os.path.exists(lock_dir))

        cmd.release_all_state_locks(contract_state_path=state_path)

        # assert lock exists
        self.assertFalse(os.path.exists(lock_dir))
