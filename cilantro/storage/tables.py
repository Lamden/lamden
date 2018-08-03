from cilantro.logger import get_logger
import json, os
from seneca.seneca_internal.storage.mysql_executer import Executer



log = get_logger("DB Creator")

GENESIS_HASH = '0' * 64
DB_NAME = 'seneca_test'

FILE_NAME = '~/cilantro/'
KILL_FILE_TMP = '/var/lib/mysql' + '/NUKE_kill_all_die_death_terminate_go_away_stop_holding_locks.txt'
constitution_json = json.load(open(os.path.join(os.path.dirname(__file__), 'constitution.json')))


# Ensure tmp file exists...



def build_tables(ex, should_drop=True):
    from cilantro.storage.contracts import build_contracts_table, seed_contracts
    from cilantro.storage.blocks import build_blocks_table, seed_blocks
    from cilantro.storage.transactions import build_transactions_table, seed_transactions

    log.debug("Building tables with should_drop={}".format(should_drop))

    if should_drop:
        _reset_db(ex)
    else:
        log.debug("Creating database {} if it doesnt already exist".format(DB_NAME))
        ex.raw('CREATE DATABASE IF NOT EXISTS {};'.format(DB_NAME))
        ex.raw('USE {};'.format(DB_NAME))

    log.debug("Creating DB tables")
    contracts = build_contracts_table(ex, should_drop)
    blocks = build_blocks_table(ex, should_drop)
    transactions = build_transactions_table(ex, should_drop)

    # Only seed database if we just dropped it, or if storage is empty
    if should_drop or not blocks.select().run(ex):
        log.info("Seeding database...")
        seed_contracts(ex, contracts)
        seed_blocks(ex, blocks)
        seed_transactions(ex, blocks)
        log.info("Done seeding database.")

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


def _clean_tmp_file():
    try:
        # os.remove(KILL_FILE_TMP)
        os.system("rm {}".format(KILL_FILE_TMP))
    except Exception as e:
        log.error("got dat err tryna clean file..\n{}".format(e))
        pass


def _reset_db(ex):
    log.info("Dropping database named {}".format(DB_NAME))

    # try:
    #     ex.raw("kill USER root;")
    # except:
    #     pass
    _clean_tmp_file()
    build_kill_file = "select concat('KILL ',id,';') from information_schema.processlist where user='root' and " \
                      "command='Sleep' into outfile '{}';".format(KILL_FILE_TMP)
    ex.raw(build_kill_file)

    # Nuke all sql processes so none of them hold a lock ... kill them delete them destroy them get them out of here
    with open(KILL_FILE_TMP, 'r') as f:
        lines = f.readlines()
        for cmd in lines:
            log.important3("executing command {}".format(cmd))
            try:
                ex.raw(cmd)
            except:
                pass

    # ex = Executer('root', '', '', '127.0.0.1')
    ex.raw('DROP DATABASE IF EXISTS {};'.format(DB_NAME))
    ex.raw('CREATE DATABASE IF NOT EXISTS {};'.format(DB_NAME))
    ex.raw('USE {};'.format(DB_NAME))

    _clean_tmp_file()
