from cilantro.logger import get_logger
from cilantro.utils import Hasher
from cilantro.db.tables import create_table
import seneca.seneca_internal.storage.easy_db as t
from seneca.execute_sc import execute_contract
import datetime
import os


log = get_logger("ContractsTable")

path = os.path.abspath(__file__)
dir_path = os.path.dirname(path)
CONTRACTS_DIR = "{}/../contracts".format(dir_path)

GENESIS_AUTHOR = 'default_cilantro_contract'
GENESIS_DATE = datetime.datetime(datetime.MINYEAR, 1, 1)


def build_contracts_table(ex, should_drop=True):
    contracts = t.Table('smart_contracts',
                        t.Column('contract_id', t.str_len(64), True),  # why is str_len(64) not working? is printing an insert statement with a value of only length 50 even when inserting a 64 char string
                        [
                            t.Column('code_str', str),
                            t.Column('author', t.str_len(64)),
                            t.Column('execution_datetime', datetime.datetime),  # why won't datetime.datetime work???
                            t.Column('execution_status', t.str_len(30)),
                        ])

    return create_table(ex, contracts, should_drop)


def seed_contracts(ex, contracts_table):
    """
    Seeds the contracts table with all contracts found in cilantro/contracts
    """
    # Insert contract code into table
    for contract_id, code_str in _read_contract_files():
        contracts_table.insert([{
            'contract_id': contract_id,
            'code_str': code_str,
            'author': GENESIS_AUTHOR,
            'execution_datetime': GENESIS_DATE,
            'execution_status': 'pending',
        }]).run(ex)

    # Run contracts
    for contract_id, code_str in _read_contract_files():
        _execute_contract(ex, contracts_table, contract_id, code_str)


def lookup_contract_code(executor, contract_id: str, contract_table) -> str:
    """
    Looks up the code for a contract by id. Returns an empty string if it could not be found.
    :param contract_id: The id (just the filename currently) of the contract to lookup
    :return: The code for the contract_id, as a string, or the empty string '', if no record could be found
    """
    query = contract_table.select('code_str').where(contract_table.contract_id == contract_id).run(executor)
    # print("got result from query: \n{}".format(query))
    assert len(query.rows) <= 1, "Multiple rows found for contract_id {}".format(contract_id)

    if len(query.rows) == 0:
        log.warning("[inside lookup_contract_code] No contract row found for contract_id {}".format(contract_id))
        return ''

    return query.rows[0][0]


def _execute_contract(executor, contract_table, contract_id: str, code_str: str, user_id=GENESIS_AUTHOR):
    def ft_module_loader(contract_name):
        log.debug("[inside _execute_contract] Attempting to load contract with id {}".format(contract_name))
        code = lookup_contract_code(executor, contract_name, contract_table)
        assert code, "No code for contract id '{}' could be found".format(contract_name)
        return this_contract_run_data, code

    log.debug("[inside _execute_contract] Executing contract with id {} and user_id {}".format(contract_id, user_id))

    global_run_data = {'caller_user_id': user_id, 'execution_datetime': None, 'caller_contract_id': contract_id}
    this_contract_run_data = {'author': user_id, 'execution_datetime': None, 'contract_id': contract_id}

    execute_contract(global_run_data, this_contract_run_data, code_str, is_main=True,
                     module_loader=ft_module_loader, db_executer=executor)


def _read_contract_files() -> list:
    """
    Reads all contracts in the cilantro/contracts directory.
    :return: A list of tuples containing (contract_hash, contract_code). Both values are strings
    """
    log.debug("Loading smart contracts at directory {}".format(CONTRACTS_DIR))
    contracts = []

    for filename in os.listdir(CONTRACTS_DIR):
        _validate_filename(filename)
        log.info("[inside _read_contract_files] Loading contract code for file {}".format(filename))

        with open('{}/{}'.format(CONTRACTS_DIR, filename), 'r') as f:
            code_str = f.read()
            assert len(code_str) > 0, "Empty code string for filename {}".format(filename)

            contract_id = _contract_id_for_filename(filename)

            contracts.append((contract_id, code_str))

            # TODO remove this (debug lines)
            max_len = min(len(code_str), 60)
            log.debug("[inside _read_contract_files] filename {} has contract_id {} has author {} and code has code: \n {} ....[SNIPPED TRUNCATED]"
                      .format(filename, contract_id, GENESIS_AUTHOR, code_str[0:max_len]))
            # end debug

    return contracts


def _contract_id_for_filename(filename):
    """
    Returns the contract_id associated with a filename

    For now this is just the filename without the extensions (ie 'hello.seneca' -> 'hello')
    """
    # contract_id = Hasher.hash(filename)
    contract_id = filename.split('.')[0]

    return contract_id


def _validate_filename(filename):
    """
    Ensures filename has a proper .seneca extension
    :return: None
    :raises: An assertion if the filename is invalid
    """
    err_str = "file named {} is not a valid smart contract (must be a .seneca file)".format(filename)
    assert filename, "Got filename that is empty string"

    dot_idx = filename.find('.')
    assert dot_idx, err_str

    extension = filename[dot_idx+1:]
    assert extension == 'seneca', err_str
