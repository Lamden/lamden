from cilantro.db import *
from unittest import TestCase
from seneca.seneca_internal.storage.mysql_executer import Executer
from cilantro.db.blocks import *
from cilantro.db.contracts import *
from cilantro.db.contracts import _read_contract_files, _contract_id_for_filename, _lookup_contract_info
import unittest
import time


CONTRACT_FILENAME = 'currency.seneca'
EXPECTED_SNIPPET = '# UNITTEST_FLAG_CURRENCY_SENECA 1729'


class TestBuildTables(TestCase):

    def _default_ex(self):
        return Executer.init_local_noauth_dev()

    def test_tables_not_none(self):
        ex = self._default_ex()
        tables = build_tables(ex, should_drop=True)

        assert tables.blocks
        assert tables.contracts

    def test_seed_blocks(self):
        ex = self._default_ex()
        tables = build_tables(ex, should_drop=True)

        blocks = tables.blocks.select().run(ex)
        expected_row = {'number': 1, 'hash': GENESIS_HASH, 'tree': GENESIS_TREE, 'signatures': GENESIS_SIGS}

        assert len(blocks.rows) == 1, "Expected blocks table to be seed with 1 row"
        row = blocks.rows[0]

        for key, expected_val in expected_row.items():
            i = blocks.keys.index(key)
            assert i >= 0, 'Key {} not found in block table keys {}'.format(key, blocks.keys)

            actual_val = row[i]
            assert actual_val == expected_val, "Blocks table key {} seeded with value {} but expected {}"\
                                               .format(key, actual_val, expected_val)

    def test_seed_contracts(self):
        ex = self._default_ex()
        tables = build_tables(ex, should_drop=True)

        query = tables.contracts.select().run(ex)

        cols = query.keys
        col_indx = {col: cols.index(col) for col in cols}

        assert 'contract_id' in cols, "Expected col named contract_id"
        assert 'code_str' in cols, "Expected col named code_str"
        assert 'author' in cols, "Expected col named author"
        assert 'execution_datetime' in cols, "Expected col named execution_datetime"
        assert 'execution_status' in cols, "Expected col named execution_status"

        contracts = _read_contract_files()

        self.assertEqual(len(contracts), len(query.rows))

        for col in query.rows:
            contract_id = col[col_indx['contract_id']]
            code_str = col[col_indx['code_str']]
            author = col[col_indx['author']]
            execution_datetime = col[col_indx['execution_datetime']]
            execution_status = col[col_indx['execution_status']]

            contract_found = False

            for _contract_id, _code_str in contracts:
                if contract_id == _contract_id and code_str == _code_str:
                    contract_found = True
                    break

            if not contract_found:
                raise Exception("Contract with id {} and not found.\ncode str ... \n{}".format(contract_id, code_str))

    def test_lookup_contract_info(self):
        ex = self._default_ex()
        tables = build_tables(ex, should_drop=True)

        contract_id = _contract_id_for_filename(CONTRACT_FILENAME)

        expected_author = GENESIS_AUTHOR
        expected_exec_dt = GENESIS_DATE
        expected_snippet = EXPECTED_SNIPPET

        actual_author, actual_exec_dt, actual_code = _lookup_contract_info(ex, tables.contracts, contract_id)

        self.assertEqual(expected_author, actual_author)
        self.assertEqual(expected_exec_dt , actual_exec_dt)
        self.assertTrue(expected_snippet in actual_code)

    def test_module_loader_fn(self):
        ex = self._default_ex()
        tables = build_tables(ex, should_drop=True)

        loader_fn = module_loader_fn(ex, tables.contracts)

        contract_id = _contract_id_for_filename(CONTRACT_FILENAME)

        author = GENESIS_AUTHOR
        execution_dt = GENESIS_DATE

        expected_run_data = {'author': author, 'execution_datetime': execution_dt, 'contract_id': contract_id}
        expected_snipped = EXPECTED_SNIPPET

        actual_run_data, actual_code = loader_fn(contract_id)

        self.assertTrue(expected_snipped in actual_code)
        self.assertEquals(expected_run_data, actual_run_data)


if __name__ == '__main__':
    unittest.main()

