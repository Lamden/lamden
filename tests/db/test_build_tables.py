from cilantro.db import *
from unittest import TestCase
from seneca.seneca_internal.storage.mysql_executer import Executer


class TestBuildTables(TestCase):

    def default_ex(self):
        return Executer.init_local_noauth_dev()

    def test_tables_not_none(self):
        ex = self.default_ex()

        tables = build_tables(ex, should_drop=True)

        assert tables.blocks
        assert tables.contracts