from cilantro.db import *
from unittest import TestCase
from seneca.seneca_internal.storage.mysql_executer import Executer
from cilantro.db.blocks_table import *
from cilantro.db.contracts_table import *
from cilantro.db.contracts_table import _read_contract_files


class TestBuildTables(TestCase):

    def default_ex(self):
        return Executer.init_local_noauth_dev()

    def test_tables_not_none(self):
        ex = self.default_ex()

        tables = build_tables(ex, should_drop=True)

        assert tables.blocks
        assert tables.contracts

    def test_seed_blocks(self):
        ex = self.default_ex()

        tables = build_tables(ex, should_drop=True)

        blocks = tables.blocks.select().run(ex)
        expected_row = {'number': 1, 'hash': GENESIS_HASH, 'tree': GENESIS_TREE, 'signatures': GENESIS_SIGS}

        assert len(blocks.rows) == 1, "Expected blocks table to be seed with 1 row"
        row = blocks.rows[0]

        for key, expected_val in expected_row.items():
            i = blocks.keys.index(key)
            assert i >= 0, 'Key {} not found in block table keys {}'.format(key, blocks.keys)

            actual_val = row[i]
            assert actual_val == expected_val, "Blocks table key {} seeded with value {} but expected {}".format(key, actual_val, expected_val)

    def test_seed_contracts(self):
        ex = self.default_ex()

        tables = build_tables(ex, should_drop=True)

        query = tables.contracts.select().run(ex)
        # print("got contracts: {}".format(query))

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

    def test_contract_lookup(self):
        ex = self.default_ex()

        tables = build_tables(ex, should_drop=True)
        contracts_table = tables.contracts

        actual_code = lookup_contract_code(ex, 'currency.seneca', contracts_table)
        expected_snipped = "# UNITTEST_FLAG_CURRENCY_SENECA"

        self.assertTrue(expected_snipped in actual_code)

    def test_contract_lookup_doesnt_exist(self):
        ex = self.default_ex()

        tables = build_tables(ex, should_drop=True)
        contracts_table = tables.contracts

        contract_code = lookup_contract_code(ex, 'i_dont_exist_1729.seneca', contracts_table)

        self.assertEqual(contract_code, '')


