from cilantro.db import *
from unittest import TestCase
from datetime import datetime

from seneca.execute_sc import execute_contract
from seneca.seneca_internal.storage.mysql_executer import Executer


class TestRunContracts(TestCase):

    def default_ex(self):
        return Executer.init_local_noauth_dev()

    def test_run_contract(self):
        def ft_module_loader(contract_id):
            return global_run_data, contract_code

        ex = self.default_ex()
        tables = build_tables(ex, should_drop=True)

        contract_id = 'rbac.seneca'
        user_id = 'god'

        contract_code = lookup_contract_code(ex, contract_id, tables.contracts)
        assert contract_code is not None, 'comon you amateur why is ur contract code None'

        global_run_data = {'caller_user_id': user_id, 'execution_datetime': None, 'caller_contract_id': contract_id}
        this_contract_run_data = {'author': user_id, 'execution_datetime': None, 'contract_id': contract_id}

        execute_contract(global_run_data, this_contract_run_data, contract_code, is_main=True,
                         module_loader=ft_module_loader, db_executer=ex)


