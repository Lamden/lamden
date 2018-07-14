from cilantro.logger import get_logger
import json, os


log = get_logger("DB Creator")

GENESIS_HASH = '0' * 64
DB_NAME = 'seneca_test'

constitution_json = json.load(open(os.path.join(os.path.dirname(__file__), 'constitution.json')))


def build_tables(ex, should_drop=True):
    from cilantro.db.contracts import build_contracts_table, seed_contracts
    from cilantro.db.blocks import build_blocks_table, seed_blocks
    from cilantro.db.transactions import build_transactions_table, seed_transactions

    if should_drop:
        _reset_db(ex)
    else:
        ex.raw('CREATE DATABASE IF NOT EXISTS {};'.format(DB_NAME))
        ex.raw('USE {};'.format(DB_NAME))

    # Create tables
    contracts = build_contracts_table(ex, should_drop)
    blocks = build_blocks_table(ex, should_drop)
    transactions = build_transactions_table(ex, should_drop)

    # Only seed database if we just dropped it
    if should_drop:
        seed_contracts(ex, contracts)
        seed_blocks(ex, blocks)
        seed_transactions(ex, blocks)

    tables = type('Tables', (object,), {'contracts': contracts, 'blocks': blocks, 'transactions': transactions})

    return tables


def create_table(ex, table, should_drop):
    if should_drop:
        try:
            table.drop_table().run(ex)
        except Exception as e:
            if e.args[0]['error_code'] == 1051:
                pass
            else:
                raise

    table.create_table(if_not_exists=True).run(ex)

    return table


def _reset_db(ex):
    log.info("Dropping database named {}".format(DB_NAME))
    ex.raw('DROP DATABASE IF EXISTS {};'.format(DB_NAME))
    ex.raw('CREATE DATABASE IF NOT EXISTS {};'.format(DB_NAME))
    ex.raw('USE {};'.format(DB_NAME))
