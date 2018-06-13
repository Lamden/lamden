from cilantro.logger import get_logger
import json, os


log = get_logger("DB Creator")

GENESIS_HASH = '0' * 64

constitution_json = json.load(open(os.path.join(os.path.dirname(__file__), 'constitution.json')))


def build_tables(ex, should_drop=True):
    from cilantro.db.contracts import build_contracts_table, seed_contracts
    from cilantro.db.blocks import build_blocks_table, seed_blocks
    from cilantro.db.balances import seed_balances

    if should_drop:
        log.info("Dropping Seneca database")
        ex.raw('DROP DATABASE IF EXISTS seneca_test;')
        ex.raw('CREATE DATABASE seneca_test;')
        ex.raw('USE seneca_test;')

    contracts = build_contracts_table(ex, should_drop)
    blocks = build_blocks_table(ex, should_drop)

    # Only seed database if we just dropped it
    if should_drop:
        # Seed tables created by Cilantro
        seed_contracts(ex, contracts)
        seed_blocks(ex, blocks)

        # Seed smart contract tables
        seed_balances(ex)


    tables = type('Tables', (object,), {'contracts': contracts, 'blocks': blocks})

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

    table.create_table().run(ex)
    return table
