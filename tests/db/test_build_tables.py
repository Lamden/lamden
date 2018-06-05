from cilantro.db import *
from unittest import TestCase
from seneca.seneca_internal.storage.mysql_executer import Executer
from cilantro.db.blocks_table import *
from cilantro.db.contracts_table import *


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

        # print("got blocks: {}".format(blocks))

        assert len(blocks.rows) == 1, "Expected blocks table to be seed with 1 row"
        row = blocks.rows[0]

        for key, expected_val in expected_row.items():
            i = blocks.keys.index(key)
            assert i >= 0, 'Key {} not found in block table keys {}'.format(key, blocks.keys)

            actual_val = row[i]
            assert actual_val == expected_val, "Blocks table key {} seeded with value {} but expected {}".format(key, actual_val, expected_val)

    def test_seed_contracts(self):
        # TODO fix and implement
        ex = self.default_ex()

        tables = build_tables(ex, should_drop=True)

        contracts = tables.contrats.select()
        print("got contracts: {}".format(contracts))

    def test_contract_lookup(self):
        # TODO implement
        pass
