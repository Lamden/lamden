from cilantro.db import *
from unittest import TestCase
import unittest
from datetime import datetime
from cilantro.logger import get_logger
from seneca.execute_sc import execute_contract
from seneca.seneca_internal.storage.mysql_executer import Executer


log = get_logger("TestRunner")


CODE_STR = \
"""
import rbac

rbac.create_user('new_user', 'admin')
"""


class TestRunContracts(TestCase):

    def default_ex(self):
        return Executer.init_local_noauth_dev()

    def test_run_contract(self):
        ex = self.default_ex()
        tables = build_tables(ex, should_drop=True)

        contract_id = 'using_rbac_1'
        user_id = 'god'

        contract_code = CODE_STR
        assert contract_code

        global_run_data = {'caller_user_id': user_id, 'execution_datetime': None, 'caller_contract_id': contract_id}
        this_contract_run_data = {'author': user_id, 'execution_datetime': None, 'contract_id': contract_id}

        execute_contract(global_run_data, this_contract_run_data, contract_code, is_main=True,
                         module_loader=module_loader_fn(ex, tables.contracts), db_executer=ex)



if __name__ == '__main__':
    unittest.main()
