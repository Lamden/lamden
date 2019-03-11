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


def seed_contracts():
    """
    Seeds the contracts table with all contracts found in cilantro_ee/contracts
    """
    log.debugv("Setting up Seneca's Executor to publish contracts.")

    interface = Executor(concurrency=False, currency=False)

    log.debug("Inserting contract code...")
    # Insert contract code from files in file system into database table
    for contract_id, code_str in _read_contract_files():
        log.spam("Publishing contract with id {}".format(contract_id))
        interface.publish_code_str(contract_id, GENESIS_AUTHOR, code_str)

    log.debug("Seeding contracts...")
    # Run contracts
    for contract_id, code_str in _read_contract_files():
        code_obj = interface.get_code_obj(contract_id)

    log.debug("Done seeding contracts.")

    if SHOULD_MINT_WALLET:
        start = time.time()
        log.info("Minting {} wallets with amount {}".format(NUM_WALLETS_TO_MINT, MINT_AMOUNT))
        for keypair in ALL_WALLETS:
            sk, vk = keypair

            interface.execute_function(module_path='seneca.contracts.currency.mint', sender=GENESIS_AUTHOR,
                                       stamps=None, to=vk, amount=MINT_AMOUNT)
        log.info("Done minting {} wallets ({} seconds elapsed)"
                 .format(NUM_WALLETS_TO_MINT, round(time.time()-start, 2)))


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
