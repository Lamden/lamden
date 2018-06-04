from cilantro.logger import get_logger
import seneca.seneca_internal.storage.easy_db as t
from seneca.seneca_internal.storage.mysql_executer import Executer
from datetime import datetime


log = get_logger("DB Creator")

GENESIS_HASH = '0' * 64


def build_tables(ex, should_drop=True):
    from cilantro.db.contracts_table import build_contracts_table, seed_contracts

    contracts = build_contracts_table(ex, should_drop)
    blocks = build_blocks_table(ex, should_drop)

    seed_contracts(ex, contracts)
    seed_blocks(ex, blocks)

    tables = type('Tables', (object,), {'contracts': contracts, 'blocks': blocks})

    return tables


def build_blocks_table(ex, should_drop=True):
    blocks = t.Table('blocks',
                     t.AutoIncrementColumn('number'),
                     [
                         t.Column('hash', t.str_len(64), True),
                         t.Column('tree', str),
                         t.Column('signatures', str),
                     ])

    return create_table(ex, blocks, should_drop)


def seed_blocks(ex, blocks_table):
    blocks_table.insert([{
            'hash': GENESIS_HASH,
            'tree': '',
            'signatures': '',
        }]).run(ex)


def create_table(ex, table, should_drop):
    if should_drop:
        try:
            table.drop_table().run(ex)
        except Exception as e:
            if e.args[0]['error_code'] == 1051:
                pass
            else:
                raise

    table.create_table().run(ex)
    return table
