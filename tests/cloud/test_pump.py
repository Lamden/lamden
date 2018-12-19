from cilantro.utils.test.testnet_config import set_testnet_config
set_testnet_config('4-4-4.json')

from cilantro.constants.vmnet import get_config_file
from vmnet.cloud.testcase import AWSTestCase
import unittest, time, random, vmnet, cilantro, os
from os.path import join, dirname
from cilantro.utils.test.mp_test_case import vmnet_test
from cilantro.utils.test.god import God
from cilantro.logger.base import get_logger
from cilantro.utils.test.god import God
from cilantro.logger import get_logger, overwrite_logger_level
import logging, os, shutil, time
from cilantro.constants.system_config import *


def wrap_func(fn, *args, **kwargs):
    def wrapper():
        return fn(*args, **kwargs)
    return wrapper


def run_mn(slot_num):
    # We must set this env var before we import anything from cilantro
    import os
    os.environ["NONCE_DISABLED"] = "1"

    from cilantro.logger import get_logger, overwrite_logger_level
    from cilantro.nodes.factory import NodeFactory
    from cilantro.constants.testnet import TESTNET_MASTERNODES

    # NOTE setting the log level below 11 does not work for some reason --davis
    # overwrite_logger_level(logging.WARNING)
    # overwrite_logger_level(21)
    overwrite_logger_level(11)

    ip = os.getenv('HOST_IP')
    sk = TESTNET_MASTERNODES[slot_num]['sk']
    NodeFactory.run_masternode(ip=ip, signing_key=sk, reset_db=True)


def run_witness(slot_num):
    from cilantro.logger import get_logger, overwrite_logger_level
    from cilantro.nodes.factory import NodeFactory
    from cilantro.constants.testnet import TESTNET_WITNESSES
    import os
    import logging

    # overwrite_logger_level(logging.WARNING)
    # overwrite_logger_level(21)
    overwrite_logger_level(11)

    w_info = TESTNET_WITNESSES[slot_num]
    w_info['ip'] = os.getenv('HOST_IP')

    NodeFactory.run_witness(ip=w_info['ip'], signing_key=w_info['sk'], reset_db=True)


def run_delegate(slot_num):
    from cilantro.logger import get_logger, overwrite_logger_level
    from seneca.libs.logger import overwrite_logger_level as sen_overwrite_log
    from cilantro.nodes.factory import NodeFactory
    from cilantro.constants.testnet import TESTNET_DELEGATES
    import os
    import logging

    # overwrite_logger_level(logging.WARNING)
    overwrite_logger_level(11)
    # sen_overwrite_log(4)  # disable spam only (lvl 5 is debugv)
    sen_overwrite_log(11)  # disable spam only (lvl 5 is debugv)

    d_info = TESTNET_DELEGATES[slot_num]
    d_info['ip'] = os.getenv('HOST_IP')

    NodeFactory.run_delegate(ip=d_info['ip'], signing_key=d_info['sk'], reset_db=True)


def pump_it(lamd, use_poisson, pump_wait):
    from cilantro.utils.test.god import God
    from cilantro.logger import get_logger, overwrite_logger_level
    import logging, time

    overwrite_logger_level(logging.WARNING)

    log = get_logger("Pumper")

    log.important("Pumper sleeping {} seconds before starting...".format(pump_wait))
    time.sleep(pump_wait)

    log.important("Starting the pump..")
    God.pump_it(rate=lamd, use_poisson=use_poisson)


class TestPump(AWSTestCase):

    NUM_BLOCKS = 2
    VOLUME = TRANSACTIONS_PER_SUB_BLOCK * NUM_SB_PER_BLOCK * NUM_BLOCKS  # Number of transactions to dum
    config_file = get_config_file('cilantro-aws-4-4-4.json')
    keep_up = True
    logging = True

    # Avg number of transactions per second we will dump. Set to dump 1 block per BATCH_SLEEP_INTERVAL
    PUMP_RATE = (TRANSACTIONS_PER_SUB_BLOCK * NUM_SB_PER_BLOCK) // BATCH_SLEEP_INTERVAL
    MODEL_AS_POISSON = True
    PUMP_WAIT = 120  # how long to sleep before we start the pump

    def test_dump(self):
        log = get_logger("Pumpatron")

        # Bootstrap master
        for i, nodename in enumerate(self.groups['masternode']):
            self.execute_python(nodename, wrap_func(run_mn, i))

        # Bootstrap witnesses
        for i, nodename in enumerate(self.groups['witness']):
            self.execute_python(nodename, wrap_func(run_witness, i))

        # Bootstrap delegates
        for i, nodename in enumerate(self.groups['delegate']):
            self.execute_python(nodename, wrap_func(run_delegate, i))

        # Bootstrap pump
        self.execute_python('mgmt', wrap_func(pump_it, self.PUMP_RATE, self.MODEL_AS_POISSON, self.PUMP_WAIT))

        # TODO also allow user to dump also??


if __name__ == '__main__':
    unittest.main()
