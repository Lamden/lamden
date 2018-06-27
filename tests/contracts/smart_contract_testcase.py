from unittest import TestCase
from cilantro.db import *
from cilantro.logger import get_logger
from cilantro.db.contracts import run_contract
from seneca.execute_sc import execute_contract
from seneca.seneca_internal.storage.mysql_executer import Executer

class SamrtContractTestCase(TestCase):

    def setUp(self):
        super().setUp()
        self.ex = Executer.init_local_noauth_dev()
        self.tables = build_tables(self.ex, should_drop=True)

    def run_contract(self, code_str, user_id='tester'):
        run_contract(self.ex, self.tables.contracts, code_str=code_str, user_id=user_id)

    def tearDown(self):
        super().tearDown()
        self.ex.cur.close()
        self.ex.conn.close()
