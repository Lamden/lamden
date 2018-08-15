from vmnet.testcase import BaseNetworkTestCase
import unittest, time, random, vmnet
from cilantro.utils.test.mp_test_case import vmnet_test

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
    overwrite_logger_level(21)

    ip = os.getenv('HOST_IP') #Constants.Testnet.Masternodes[0]['ip']
    sk = TESTNET_MASTERNODES[0]['sk']
    NodeFactory.run_masternode(ip=ip, signing_key=sk, reset_db=True)


def run_witness(slot_num):
    from cilantro.logger import get_logger, overwrite_logger_level
    from cilantro.nodes import NodeFactory
    from cilantro.constants.testnet import TESTNET_WITNESSES
    import os
    import logging

    # overwrite_logger_level(logging.WARNING)
    overwrite_logger_level(15)

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
    overwrite_logger_level(21)

    d_info = TESTNET_DELEGATES[slot_num]
    d_info['ip'] = os.getenv('HOST_IP')

    NodeFactory.run_delegate(ip=d_info['ip'], signing_key=d_info['sk'], reset_db=True)


def dump_it(volume, delay=30):
    from cilantro.utils.test import God
    from cilantro.logger import get_logger, overwrite_logger_level
    import logging

    overwrite_logger_level(logging.WARNING)
    God.dump_it(volume=volume, delay=delay)


class TestDump(BaseNetworkTestCase):

    VOLUME = 1000  # Number of transactions to dump
    config_file = 'configs/test-vmnet-v2.json'

    @vmnet_test(run_webui=True)
    def test_dump(self):

        # Bootstrap master
        self.execute_python('masternode', run_mn, profiling='p')

        # Bootstrap TESTNET_WITNESSES
        for i, nodename in enumerate(self.groups['witness']):
            self.execute_python(nodename, wrap_func(run_witness, i))

        # Bootstrap TESTNET_DELEGATES
        for i, nodename in enumerate(self.groups['delegate']):
            self.execute_python(nodename, wrap_func(run_delegate, i), profiling='p')

        self.execute_python('mgmt', wrap_func(dump_it, volume=self.VOLUME, delay=16))

        input("Enter any key to terminate")

if __name__ == '__main__':
    unittest.main()
