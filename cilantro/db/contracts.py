from cilantro.logger import get_logger
from cilantro.utils import Hasher
from cilantro.db.tables import create_table
import seneca.seneca_internal.storage.easy_db as t
from seneca.execute_sc import execute_contract, get_read_only_contract_obj as get_exports
import datetime
import os


log = get_logger("ContractsTable")

path = os.path.abspath(__file__)
dir_path = os.path.dirname(path)
CONTRACTS_DIR = "{}/../contracts/lib".format(dir_path)

GENESIS_AUTHOR = 'default_cilantro_contract'
GENESIS_DATE = datetime.datetime(datetime.MINYEAR, 1, 1)


def build_contracts_table(ex, should_drop=True):
    contracts = t.Table('smart_contracts',
                        t.Column('contract_id', t.str_len(64), True),
                        [
                            t.Column('code_str', str),
                            t.Column('author', t.str_len(64)),
                            t.Column('execution_datetime', datetime.datetime),
                            t.Column('execution_status', t.str_len(30)),
                        ])

    return create_table(ex, contracts, should_drop)


def seed_contracts(ex, contracts_table):
    """
    Seeds the contracts table with all contracts found in cilantro/contracts
    """
    # Insert contract code from files in file system into database table
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
        run_contract(ex, contracts_table, contract_id)


def module_loader_fn(ex, contract_table):
    """
    Returns a module loader function used for executing contracts
    :return: A function which takes a single parameter, a contract_id, and returns a tuple of (contract_data, code_str)
    """
    def _module_loader_fn(contract_id: str) -> tuple:
        author, exec_dt, code_str = _lookup_contract_info(ex, contract_table, contract_id)
        runtime_data = {'author': author, 'contract_id': contract_id, 'execution_datetime': exec_dt}

        return runtime_data, code_str

    return _module_loader_fn


# def run_contract(executor, contract_table, contract_id: str='', user_id=GENESIS_AUTHOR, code_str: str=''):
#     assert bool(contract_id) ^ bool(code_str), "Either contract_id or code_str must be passed in (XOR, one or the other)"
#     log.debug("[inside _execute_contract] Executing contract with id {} and user_id {}".format(contract_id, user_id))
#
#     if code_str:
#         author = user_id
#         exec_dt = None  # todo make this current datetime
#     else:
#         author, exec_dt, code_str = _lookup_contract_info(executor, contract_table, contract_id)
#
#     global_run_data = {'caller_user_id': user_id, 'execution_datetime': exec_dt, 'caller_contract_id': contract_id}
#     this_contract_run_data = {'author': author, 'execution_datetime': exec_dt, 'contract_id': contract_id}
#
#     result = execute_contract(global_run_data, this_contract_run_data, code_str, is_main=True,
#                               module_loader=module_loader_fn(executor, contract_table), db_executer=executor)
#
#     log.debug("\n result of executor contract with id {}: \n {} \n\n".format(contract_id, result))
#
#     return result

def _ex_contract(executor, contract_table, contract_id: str='', user_id=GENESIS_AUTHOR, code_str: str='', get_contract=False):
        assert bool(contract_id) ^ bool(code_str), "Either contract_id or code_str must be passed in (XOR, one or the other)"
        log.debug("[inside _execute_contract] Executing contract with id {} and user_id {}".format(contract_id, user_id))

        if code_str:
            author = user_id
            exec_dt = None  # todo make this current datetime
        else:
            author, exec_dt, code_str = _lookup_contract_info(executor, contract_table, contract_id)

        global_run_data = {'caller_user_id': user_id, 'execution_datetime': exec_dt, 'caller_contract_id': contract_id}
        this_contract_run_data = {'author': author, 'execution_datetime': exec_dt, 'contract_id': contract_id}

        _ex_func = get_exports if get_contract else execute_contract
        result = _ex_func(global_run_data, this_contract_run_data, code_str,
                                  module_loader=module_loader_fn(executor, contract_table), db_executer=executor)

        return result


def get_contract_exports(*args, **kwargs):
    return _ex_contract(*args, **kwargs, get_contract=True)


def run_contract(*args, **kwargs):
    return _ex_contract(*args, **kwargs, get_contract=False)


def _lookup_contract_info(executor, contract_table, contract_id: str) -> tuple:
    """
    Looks up the contract info for the specified contract id. This includes the author, execution datetime, and code
    string. These values a returned in a tuple of that order.
    :param contract_id: The id of the contract to lookup
    :return: A tuple, containing 3 elements (author: str, execution_datetime: datetime.datetime, code_str: str)
    :raises: An exception if the contract_id cannot be found
    """
    query = contract_table.select().where(contract_table.contract_id == contract_id).run(executor)

    assert len(query.rows) > 0, "No rows found for contract_id {}".format(contract_id)
    assert len(query.rows) <= 1, "Multiple rows found for contract_id {}".format(contract_id)

    author = query[0]['author']
    exec_dt = query[0]['execution_datetime']
    code_str = query[0]['code_str']

    assert len(code_str) > 0, 'Contract id {} with author {} has empty code string'.format(contract_id, author)

    return author, exec_dt, code_str


def _read_contract_files() -> list:
    """
    Reads all contracts in the cilantro/contracts directory.
    :return: A list of tuples containing (contract_id, contract_code). Both values are strings
    """
    log.debug("Loading smart contracts at directory {}".format(CONTRACTS_DIR))
    contracts = []

    for filename in sorted(os.listdir(CONTRACTS_DIR)):
        _validate_filename(filename)
        log.info("[inside _read_contract_files] Loading contract code for file {}".format(filename))

        with open('{}/{}'.format(CONTRACTS_DIR, filename), 'r') as f:
            code_str = f.read()
            assert len(code_str) > 0, "Empty code string for filename {}".format(filename)

            contract_id = _contract_id_for_filename(filename)

            contracts.append((contract_id, code_str))

            # TODO remove this (debug lines)
            # max_len = min(len(code_str), 60)
            # log.debug("[inside _read_contract_files] filename {} has contract_id {} has author {} and code has code: "
            #           "\n {} ....[SNIPPED TRUNCATED]"
            #           .format(filename, contract_id, GENESIS_AUTHOR, code_str[0:max_len]))
            # end debug

    return contracts


def _contract_id_for_filename(filename):
    """
    Returns the contract_id associated with a filename

    For now this is just the filename without the extensions (ie 'hello.seneca' -> 'hello')
    """
    _validate_filename(filename)

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
