from vmnet.test.base import *
import unittest, time
from cilantro.constants.testnet import masternodes, witnesses, delegates

def wrap_func(fn, *args, **kwargs):
    def wrapper():
        return fn(*args, **kwargs)
    return wrapper

def run_mn():
    from cilantro.logger import get_logger, overwrite_logger_level
    from cilantro.nodes import NodeFactory
    import os
    import logging

    overwrite_logger_level(logging.WARNING)

    ip = os.getenv('HOST_IP') #Constants.Testnet.Masternodes[0]['ip']
    sk = masternodes[0]['sk']
    NodeFactory.run_masternode(ip=ip, signing_key=sk)


def run_witness(slot_num):
    from cilantro.logger import get_logger, overwrite_logger_level
    from cilantro.nodes import NodeFactory
    import os
    import logging

    overwrite_logger_level(logging.WARNING)

    w_info = witnesses[slot_num]
    w_info['ip'] = os.getenv('HOST_IP')

    NodeFactory.run_witness(ip=w_info['ip'], signing_key=w_info['sk'])


def run_delegate(slot_num):
    from cilantro.logger import get_logger, overwrite_logger_level
    from cilantro.nodes import NodeFactory
    import os
    import logging

    overwrite_logger_level(logging.WARNING)

    d_info = delegates[slot_num]
    d_info['ip'] = os.getenv('HOST_IP')

    NodeFactory.run_delegate(ip=d_info['ip'], signing_key=d_info['sk'])


def pump_it(lamd, use_poisson):
    from cilantro.utils.test import God
    God.pump_it(rate=lamd, gen_func=God.random_std_tx, use_poisson=use_poisson)

class TestPump(BaseNetworkTestCase):

    EXPECTED_TRANSACTION_RATE = 0.1  # Avg transaction/second. lambda parameter in Poission distribution
    MODEL_AS_POISSON = False

    testname = 'pump_it'
    setuptime = 10
    compose_file = 'cilantro-bootstrap.yml'

    @vmnet_test(run_webui=True)
    def test_bootstrap(self):

        # Bootstrap master
        self.execute_python('masternode', run_mn, async=True)

        # Bootstrap witnesses
        for i, nodename in enumerate(self.groups['witness']):
            self.execute_python(nodename, wrap_func(run_witness, i), async=True)

        # Bootstrap delegates
        for i, nodename in enumerate(self.groups['delegate']):
            self.execute_python(nodename, wrap_func(run_delegate, i), async=True)

        # PUMP IT
        time.sleep(15)
        self.execute_python('mgmt', wrap_func(pump_it, self.EXPECTED_TRANSACTION_RATE, self.MODEL_AS_POISSON), async=True)

        input("Enter any key to terminate")

if __name__ == '__main__':
    unittest.main()
