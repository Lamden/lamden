from cilantro.storage.contracts import run_contract
from cilantro.storage.tables import build_tables
from unittest import TestCase
import unittest
from datetime import datetime
from cilantro.logger import get_logger
from seneca.execute import execute_contract
from seneca.engine.storage.mysql_executer import Executer
from cilantro.storage.templating import ContractTemplate
from cilantro.constants.db import DB_SETTINGS


log = get_logger("TestRunner")


USING_RBAC_CODE = \
"""
import rbac

rbac.create_user('pepe', 'admin')
rbac.create_user('jesus', 'admin')

rbac.create_role('incompetent_buffoon', False, False, False, False, False)
rbac.create_user('trumpster dumpster', 'incompetent_buffoon')
"""


USING_CURRENCY_CODE = \
"""
import currency

currency.transfer_coins('CARL', 10 ** 6)
"""


class TestRunContracts(TestCase):

    def setUp(self):
        super().setUp()

        self.ex = Executer(**DB_SETTINGS)

    def tearDown(self):
        super().tearDown()

        self.ex.cur.close()
        self.ex.conn.close()

    def test_run_contract(self):
        tables = build_tables(self.ex, should_drop=True)

        run_contract(self.ex, tables.contracts, code_str=USING_RBAC_CODE, user_id='DAVIS')

        # TODO assert that the new user was created as expected

    def test_run_currency(self):
        tables = build_tables(self.ex, should_drop=True)

        run_contract(self.ex, tables.contracts, code_str=USING_CURRENCY_CODE, user_id='DAVIS')

       # TODO assert that currency transfer actually happened (do raw storage queries or something)

    def test_run_currency_with_template(self):
        tables = build_tables(self.ex, should_drop=True)
        code_str = ContractTemplate.interpolate_template('currency', receiver='DAVIS', amount=2 * (10 ** 6))

        run_contract(self.ex, tables.contracts, code_str=code_str, user_id='CARL')


if __name__ == '__main__':
    unittest.main()
