from vmnet.testcase import BaseNetworkTestCase
import unittest, time, cilantro
from os.path import join, dirname
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
    overwrite_logger_level(logging.DEBUG)
    # overwrite_logger_level(21)

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


def pump_it(lamd, use_poisson):
    from cilantro.utils.test import God
    from cilantro.logger import get_logger, overwrite_logger_level
    import logging

    overwrite_logger_level(logging.WARNING)

    log = get_logger("Mr. Pump")
    log.important("Starting the pump")

    God.pump_it(rate=lamd, use_poisson=use_poisson)


class TestPump(BaseNetworkTestCase):

    TRANSACTION_RATE = 50  # Avg transaction/second. lambda parameter in Poission distribution
    MODEL_AS_POISSON = True

    config_file = join(dirname(cilantro.__path__[0]), 'vmnet_configs', 'cilantro-bootstrap.json')

    @vmnet_test(run_webui=True)
    def test_bootstrap(self):

        # Bootstrap master
        self.execute_python('masternode', run_mn, async=True)

        # Bootstrap TESTNET_WITNESSES
        for i, nodename in enumerate(self.groups['witness']):
            self.execute_python(nodename, wrap_func(run_witness, i), async=True)

        # Bootstrap TESTNET_DELEGATES
        for i, nodename in enumerate(self.groups['delegate']):
            self.execute_python(nodename, wrap_func(run_delegate, i), async=True)

        # PUMP IT
        time.sleep(10)  # Wait for masternode to come online
        self.execute_python('mgmt', wrap_func(pump_it, self.TRANSACTION_RATE, self.MODEL_AS_POISSON), async=True)

        input("Enter any key to terminate")

if __name__ == '__main__':
    unittest.main()
