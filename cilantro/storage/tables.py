from cilantro.logger import get_logger
import json, os, uuid
from seneca.engine.storage.mysql_executer import Executer
from cilantro.constants.db import DB_SETTINGS


log = get_logger("DB Creator")

DB_NAME = DB_SETTINGS['db']
NUM_SNIPES = 32  # Number of times to attempt to kill a single sleeping DB cursor when resetting db

constitution_json = json.load(open(os.path.join(os.path.dirname(__file__), 'constitution.json')))


def build_tables(ex, should_drop=True):
    from cilantro.storage.contracts import build_contracts_table, seed_contracts
    # from cilantro.storage.blocks import build_blocks_table, seed_blocks
    # from cilantro.storage.transactions import build_transactions_table, seed_transactions

    log.debug("Building tables with should_drop={}".format(should_drop))

    if should_drop:
        _reset_db(ex)
    else:
        log.debug("Creating database {} if it doesnt already exist".format(DB_NAME))
        ex.raw('CREATE DATABASE IF NOT EXISTS {};'.format(DB_NAME))
        ex.raw('USE {};'.format(DB_NAME))

    log.info("Creating DB tables")
    contracts = build_contracts_table(ex, should_drop)
    # blocks = build_blocks_table(ex, should_drop)
    # transactions = build_transactions_table(ex, should_drop)

    # Only seed database if we just dropped it, or if storage is empty
    if should_drop or not contracts.select().run(ex):
        log.info("Seeding database...")
        seed_contracts(ex, contracts)
        # seed_blocks(ex, blocks)
        # seed_transactions(ex, blocks)
        log.info("Done seeding database.")

    # tables = type('Tables', (object,), {'contracts': contracts, 'blocks': blocks, 'transactions': transactions})
    tables = type('Tables', (object,), {'contracts': contracts})

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


def _assassinate_sleeping_db_cursors(ex):
    """
    Find sleeping DB cursors.
    Slay them one by one, without mercy or remorse.
    Leave no survivors.
    """
    log.debug("Killing sleeping DB cursors...")
    for _ in range(NUM_SNIPES):
        try:
            ex.raw("SET @kill_id := (select id from information_schema.processlist where command='Sleep' limit 1);")
            ex.raw("KILL (SELECT @kill_id);")
            log.debugv("Killed a DB cursor")
        except Exception as e:
            pass


def _reset_db(ex):
    log.info("Dropping database named {}".format(DB_NAME))

    _assassinate_sleeping_db_cursors(ex)

    ex.raw('DROP DATABASE IF EXISTS {};'.format(DB_NAME))
    ex.raw('CREATE DATABASE IF NOT EXISTS {};'.format(DB_NAME))
    ex.raw('USE {};'.format(DB_NAME))
