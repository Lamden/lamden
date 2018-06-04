from cilantro.logger import get_logger
from cilantro.utils import Hasher
from cilantro.db.tables import create_table
import seneca.seneca_internal.storage.easy_db as t
from seneca.seneca_internal.storage.mysql_executer import Executer
from datetime import datetime
import os


log = get_logger("ContractsTableCreator")

path = os.path.abspath(__file__)
dir_path = os.path.dirname(path)
CONTRACTS_DIR = "{}/../contracts".format(dir_path)


def build_contracts_table(ex, should_drop=True):
    contracts = t.Table('smart_contracts',
                        t.Column('contract_address', t.str_len(64), True),  # why is str_len(64) not working? is printing an insert statement with a value of only length 50 even when inserting a 64 char string
                        [
                            t.Column('code_str', str),
                            t.Column('author', t.str_len(64)),
                            t.Column('execution_datetime', datetime),
                            t.Column('execution_status', t.str_len(30)),
                        ])

    return create_table(ex, contracts, should_drop)


def seed_contracts(ex, contracts_table):
    """
    Seeds the contracts table with all contracts found in cilantro/contracts
    """
    # contract_id = 'A' * 64
    contract_id = 'test_id'
    author = 'me'

    res = contracts_table.insert([{
        'contract_address': contract_id,
        'code_str': 'dank code',
        'author': author,
        'execution_datetime:': None,
        'execution_status': 'pending'
    }]).run(ex)
    log.debug("got result from inserting contract id {}: {}".format(contract_id, res))


    # Add all contracts in CONTRACTS_DIR directory
    # log.info("Loading smart contracts at directory {}".format(CONTRACTS_DIR))
    # for filename in os.listdir(CONTRACTS_DIR):
    #     _validate_filename(filename)
    #     log.info("Loading contract code for file {}".format(filename))
    #
    #     with open('{}/{}'.format(CONTRACTS_DIR, filename), 'r') as f:
    #         code_str = f.read()
    #         contract_id = Hasher.hash(filename)
    #         author = 'default_cilantro_contract'
    #
    #         # TODO remove this (debug line)
    #         log.debug("filename {} has contract_id {} has author {} and code has code {}"
    #                   .format(filename, contract_id, author, code_str))
    #
    #         # res = contracts_table.insert([{
    #         #         'contract_id': contract_id,
    #         #         'code_str': code_str.encode().hex(),
    #         #         'author': author,
    #         #         'execution_datetime:': None,
    #         #         'execution_status': 'pending',
    #         #     }]).run(ex)
    #         res = contracts_table.insert([{
    #                 'contract_id': contract_id,
    #                 'code_str': 'while True: pass',
    #                 'author': author,
    #                 'execution_datetime:': None,
    #                 'execution_status': 'pending',
    #             }]).run(ex)
    #         log.debug("got result from inserting contract id {}: {}".format(contract_id, res))


def _validate_filename(filename):
    """
    Ensures filename is a proper .seneca file
    """
    err_str = "file named {} is not a valid smart contract (must be a .seneca file)".format(filename)
    assert filename, err_str

    dot_idx = filename.find('.')
    assert dot_idx, err_str

    extension = filename[dot_idx+1:]
    assert extension == 'seneca', err_str