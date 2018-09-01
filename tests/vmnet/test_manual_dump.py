from vmnet.testcase import BaseNetworkTestCase
import unittest, time, random, vmnet, cilantro
from os.path import join, dirname
from cilantro.utils.test.mp_test_case import vmnet_test
from cilantro.utils.test.god import God
from cilantro.logger.base import get_logger


LOG_LEVEL = 0


def wrap_func(fn, *args, **kwargs):
    def wrapper():
        return fn(*args, **kwargs)
    return wrapper


def run_mn():
    from cilantro.logger import get_logger, overwrite_logger_level
    from cilantro.nodes import NodeFactory
    from cilantro.constants.testnet import TESTNET_MASTERNODES
    import os
    import logging

    # overwrite_logger_level(logging.WARNING)
    # overwrite_logger_level(21)

    ip = os.getenv('HOST_IP')
    sk = TESTNET_MASTERNODES[0]['sk']
    NodeFactory.run_masternode(ip=ip, signing_key=sk, reset_db=True)


def run_witness(slot_num):
    from cilantro.logger import get_logger, overwrite_logger_level
    from cilantro.nodes import NodeFactory
    from cilantro.constants.testnet import TESTNET_WITNESSES
    import os
    import logging

    # overwrite_logger_level(logging.WARNING)
    # overwrite_logger_level(21)

    w_info = TESTNET_WITNESSES[slot_num]
    w_info['ip'] = os.getenv('HOST_IP')

    NodeFactory.run_witness(ip=w_info['ip'], signing_key=w_info['sk'], reset_db=True)


def run_delegate(slot_num):
    from cilantro.logger import get_logger, overwrite_logger_level
    from cilantro.nodes import NodeFactory
    from cilantro.constants.testnet import TESTNET_DELEGATES
    import os
    import logging

    # overwrite_logger_level(logging.WARNING)
    # overwrite_logger_level(21)

    d_info = TESTNET_DELEGATES[slot_num]
    d_info['ip'] = os.getenv('HOST_IP')

    NodeFactory.run_delegate(ip=d_info['ip'], signing_key=d_info['sk'], reset_db=True)


def dump_it(volume, delay=0):
    from cilantro.utils.test import God
    from cilantro.logger import get_logger, overwrite_logger_level
    import logging

    overwrite_logger_level(logging.WARNING)
    God.dump_it(volume=volume, delay=delay)


class TestManualDump(BaseNetworkTestCase):

    VOLUME = 10  # Number of transactions to dump
    config_file = join(dirname(cilantro.__path__[0]), 'vmnet_configs', 'cilantro-bootstrap.json')
    PROFILE_TYPE = None

    @vmnet_test(run_webui=True)
    def test_dump(self):
        log = get_logger("Dumpatron6000")
        log.important3("DUMPATRON6000 REPORTING FOR DUTY")

        # Bootstrap master
        self.execute_python('masternode', run_mn, async=True, profiling=self.PROFILE_TYPE)

        # Bootstrap witnesses
        for i, nodename in enumerate(self.groups['witness']):
            self.execute_python(nodename, wrap_func(run_witness, i), async=True, profiling=self.PROFILE_TYPE)

        # Bootstrap delegates
        for i, nodename in enumerate(self.groups['delegate']):
            self.execute_python(nodename, wrap_func(run_delegate, i), async=True, profiling=self.PROFILE_TYPE)

        input("Press any key to begin the dump...")
        log.important3("Dumpatron6000 dumping transactions!")
        self.execute_python('mgmt', wrap_func(dump_it, volume=self.VOLUME), async=True, profiling=self.PROFILE_TYPE)

        input("Press any key to initiate teardown")
        log.important3("Dumpatron6000 initiating system teardown")
        God.teardown_all("http://{}".format(self.ports['masternode']['8080']))


if __name__ == '__main__':
    unittest.main()
