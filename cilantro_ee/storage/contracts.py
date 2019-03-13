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


def mint_wallets():
    """
    Seeds the contracts table with all contracts found in cilantro_ee/contracts
    """
    log.debugv("Setting up Seneca's Executor to publish contracts.")

    interface = Executor(concurrency=False, currency=False)

    if SHOULD_MINT_WALLET:
        start = time.time()
        log.info("Minting {} wallets with amount {}".format(NUM_WALLETS_TO_MINT, MINT_AMOUNT))
        for keypair in ALL_WALLETS:
            sk, vk = keypair
            interface.execute_function('currency', 'mint', GENESIS_AUTHOR, kwargs={
                                           'to': vk,
                                           'amount': MINT_AMOUNT
                                       })
        log.info("Done minting {} wallets ({} seconds elapsed)"
                 .format(NUM_WALLETS_TO_MINT, round(time.time()-start, 2)))
