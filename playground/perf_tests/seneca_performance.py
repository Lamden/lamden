from cilantro.utils.test.god import God
from cilantro.storage.contracts import run_contract
from cilantro.logger.base import get_logger, overwrite_logger_level
from cilantro.storage.db import DB
from cilantro.storage.tables import DB_NAME
from cilantro.storage.templating import ContractTemplate
from cilantro.protocol.interpreter import SenecaInterpreter
from seneca.seneca_internal.storage.mysql_spits_executer import Executer
from cilantro.constants.db import DB_SETTINGS
import time


checkpoint_freq = 64
log = get_logger("SenecaTester")
RECEIVER_VK = '324ee2e3544a8853a3c5a0ef0946b929aa488cbe7e7ee31a0fef9585ce398502'
SENDER_VK = 'a103715914a7aae8dd8fddba945ab63a169dfe6e37f79b4a58bcf85bfd681694'
AMOUNT = 1


CODE_STR = \
"""
import currency
currency.transfer_coins('324ee2e3544a8853a3c5a0ef0946b929aa488cbe7e7ee31a0fef9585ce398502', 1)
"""


# def generate_contract_codes(num_contracts) -> list:
    # return [ContractTemplate.interpolate_template('currency', amount=AMOUNT, receiver=RECEIVER_VK) for _ in range(num_contracts)]
    # return [CODE_STR for _ in range(num_contracts)]


def run_contracts_in_interpreter(num_contracts=100):
    interpreter = SenecaInterpreter()

    # Generate the contracts
    log.notice("Generating {} contracts...".format(num_contracts))
    contracts = [God.random_contract_tx() for _ in range(num_contracts)]
    log.notice("Done generating contracts.")

    # Interpret them
    count = 0
    start = time.time()
    log.info("Running contracts...")
    for contract in contracts:
        interpreter._run_contract(contract)
        count += 1
        if count % checkpoint_freq == 0:
            log.notice("{} contracts run so far.".format(count))

    total_time = time.time() - start
    cps = num_contracts / total_time
    log.important("Ran {} contracts in {} seconds".format(num_contracts, round(total_time, 4)))
    log.important("{} contracts per second.".format(round(cps, 2)))

    assert interpreter.queue_size == num_contracts, "Interpreter queue size {} does not match num contracts {}..y tho"\
                                                    .format(interpreter.queue_size, num_contracts)


def run_contracts_standalone(num_contracts=100):
    ex = Executer(**DB_SETTINGS)
    with DB() as db:
        contracts_table = db.tables.contracts

    count = 0
    start = time.time()
    log.info("Running contracts...")
    for _ in range(num_contracts):
        run_contract(ex, contracts_table, contract_id=None, user_id=SENDER_VK, code_str=CODE_STR)
        count += 1
        if count % checkpoint_freq == 0:
            log.notice("{} contracts run so far.".format(count))

    total_time = time.time() - start
    cps = num_contracts / total_time
    log.important("Ran {} contracts in {} seconds".format(num_contracts, round(total_time, 4)))
    log.important("{} contracts per second.".format(round(cps, 2)))


if __name__== "__main__":
    overwrite_logger_level(20)
    # run_contracts(1000)
    run_contracts_standalone(1000)
