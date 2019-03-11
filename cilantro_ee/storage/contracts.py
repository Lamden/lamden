from cilantro_ee.logger import get_logger
from seneca.engine.interpreter.executor import Executor
from cilantro_ee.constants.system_config import *
import datetime, time
import os
from cilantro_ee.utils.test.god import ALL_WALLETS


log = get_logger("ContractSeeder")

path = os.path.abspath(__file__)
dir_path = os.path.dirname(path)
CONTRACTS_DIR = "{}/../contracts/lib".format(dir_path)

GENESIS_AUTHOR = '324ee2e3544a8853a3c5a0ef0946b929aa488cbe7e7ee31a0fef9585ce398502'
GENESIS_DATE = datetime.datetime(datetime.MINYEAR, 1, 1)


def _read_contract_files() -> list:
    """
    Reads all contracts in the cilantro_ee/contracts directory.
    :return: A list of tuples containing (contract_id, contract_code). Both values are strings
    """
    log.debug("Loading smart contracts at directory {}".format(CONTRACTS_DIR))
    contracts = []

    for filename in sorted(os.listdir(CONTRACTS_DIR)):
        _validate_filename(filename)
        # log.info("[inside _read_contract_files] Loading contract code for file {}".format(filename))

        with open('{}/{}'.format(CONTRACTS_DIR, filename), 'r') as f:
            code_str = f.read()
            assert len(code_str) > 0, "Empty code string for filename {}".format(filename)

            contract_id = _contract_id_for_filename(filename)

            contracts.append((contract_id, code_str))

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
    err_str = "file named {} is not a valid smart contract (must be a .sen.py file)".format(filename)
    assert filename, "Got filename that is empty string"

    parts = filename.split('.')
    assert len(parts), err_str
    assert parts[-2:] == ['sen', 'py'], err_str
