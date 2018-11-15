from cilantro.logger import get_logger
from cilantro.utils import Hasher
from seneca.engine.interface import SenecaInterface
import datetime
import os


log = get_logger("ContractsTable")

path = os.path.abspath(__file__)
dir_path = os.path.dirname(path)
CONTRACTS_DIR = "{}/../contracts/lib".format(dir_path)

GENESIS_AUTHOR = 'default_cilantro_contract'
GENESIS_DATE = datetime.datetime(datetime.MINYEAR, 1, 1)

def seed_contracts():
    """
    Seeds the contracts table with all contracts found in cilantro/contracts
    """
    log.debugv("Setting up SenecaInterface to publish contracts.")
    interface = SenecaInterface()

    log.debugv("Inserting contract code...")
    # Insert contract code from files in file system into database table
    for contract_id, code_str in _read_contract_files():
        interface.publish_code_str(
            contract_id,
            GENESIS_AUTHOR,
            code_str,
            keep_original=True)

    log.debugv("Seeding contracts...")
    # Run contracts
    for contract_id, code_str in _read_contract_files():
        code_obj = interface.get_code_obj(contract_id)

    log.debugv("Done seeding contracts. Tearing down SenecaInterface.")
    interface.teardown()


def _read_contract_files() -> list:
    """
    Reads all contracts in the cilantro/contracts directory.
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
    err_str = "file named {} is not a valid smart contract (must be a .sen.py file)".format(filename)
    assert filename, "Got filename that is empty string"

    parts = filename.split('.')
    assert len(parts), err_str
    assert parts[-2:] == ['sen', 'py'], err_str
