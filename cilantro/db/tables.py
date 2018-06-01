import seneca.seneca_internal.storage.easy_db as t
from seneca.seneca_internal.storage.mysql_executer import Executer
from datetime import datetime


def build_tables(ex, should_drop=True):
    contracts = _build_contracts_table(ex, should_drop)
    blocks = _build_blocks_table(ex, should_drop)

    # TODO seed /w default values

    tables = type('Tables', (object,), {'contracts': contracts, 'blocks': blocks})

    return tables


def _build_contracts_table(ex, should_drop=True):
    contracts = t.Table('smart_contracts',
                        t.Column('contract_id', t.str_len(64), True),
                        [
                            t.Column('code_str', str),
                            t.Column('author', t.str_len(64)),
                            t.Column('execution_datetime', datetime),
                            t.Column('execution_status', t.str_len(30)),
                        ])

    return _create_table(ex, contracts, should_drop)


def _build_blocks_table(ex, should_drop=True):
    blocks = t.Table('blocks',
                     t.AutoIncrementColumn('number'),
                     [
                         t.Column('hash', t.str_len(64), True),
                         t.Column('tree', str),
                         t.Column('signatures', str),
                     ])

    return _create_table(ex, blocks, should_drop)


def _create_table(ex, table, should_drop):
    if should_drop:
        try:
            table.drop_table().run(ex)
        except Exception as e:
            if e.args[0]['error_code'] == 1051:
                pass
            else:
                raise

    table.create_table().run(ex)
