from cilantro.utils.test.testnet_config import set_testnet_config
set_testnet_config('2-2-2.json')

from vmnet.testcase import BaseNetworkTestCase
import unittest, time, random, vmnet, cilantro
from os.path import join, dirname
from cilantro.utils.test.mp_test_case import vmnet_test
from cilantro.utils.test.god import God
from cilantro.logger.base import get_logger
from cilantro.utils.test.god import God
from cilantro.logger import get_logger, overwrite_logger_level
import logging

LOG_LEVEL = 0


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

    # overwrite_logger_level(logging.WARNING)
    # overwrite_logger_level(21)
    # overwrite_logger_level(11)
    # overwrite_logger_level(4)  # suppress 'spam' log level

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
    from cilantro.nodes.factory import NodeFactory
    from cilantro.constants.testnet import TESTNET_DELEGATES
    import os
    import logging

    # overwrite_logger_level(logging.WARNING)
    overwrite_logger_level(11)

    d_info = TESTNET_DELEGATES[slot_num]
    d_info['ip'] = os.getenv('HOST_IP')

    NodeFactory.run_delegate(ip=d_info['ip'], signing_key=d_info['sk'], reset_db=True)


def dump_it(volume, delay=0):
    from cilantro.utils.test.god import God
    from cilantro.logger import get_logger, overwrite_logger_level
    import logging

    overwrite_logger_level(logging.WARNING)
    God.dump_it(volume=volume, delay=delay)


class TestManualDump(BaseNetworkTestCase):

    VOLUME = 1200  # Number of transactions to dump
    config_file = join(dirname(cilantro.__path__[0]), 'vmnet_configs', 'cilantro-2-2-2-bootstrap.json')
    PROFILE_TYPE = None

    @vmnet_test(run_webui=True)
    def test_dump(self):
        log = get_logger("Dumpatron")

        # Bootstrap master
        for i, nodename in enumerate(self.groups['masternode']):
            self.execute_python(nodename, wrap_func(run_mn, i), async=True, profiling=self.PROFILE_TYPE)

        # Bootstrap witnesses
        for i, nodename in enumerate(self.groups['witness']):
            self.execute_python(nodename, wrap_func(run_witness, i), async=True, profiling=self.PROFILE_TYPE)

        # Bootstrap delegates
        for i, nodename in enumerate(self.groups['delegate']):
            self.execute_python(nodename, wrap_func(run_delegate, i), async=True, profiling=self.PROFILE_TYPE)

        while True:
            user_input = input("Enter an integer representing the # of transactions to dump, or 'x' to quit.")
            if user_input.lower() == 'x':
                log.debug("Termination input detected. Breaking")
                break

            vol = int(user_input) if user_input.isdigit() else self.VOLUME
            log.important3("Dumpatron dumping {} transactions!".format(vol))
            self.execute_python('mgmt', wrap_func(dump_it, volume=vol), async=True, profiling=self.PROFILE_TYPE)

        log.important3("Dumpatron initiating system teardown")
        God.teardown_all("http://{}".format(self.ports['masternode']['8080']))


if __name__ == '__main__':
    unittest.main()
