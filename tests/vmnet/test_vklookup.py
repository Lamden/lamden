from vmnet.testcase import BaseNetworkTestCase
import unittest, time, random
from cilantro.protocol import wallet
from cilantro.constants.testnet import TESTNET_MASTERNODES, TESTNET_WITNESSES, TESTNET_DELEGATES

import vmnet

def wrap_func(fn, *args, **kwargs):
    def wrapper():
        return fn(*args, **kwargs)
    return wrapper

def run_mn():
    from cilantro.logger import get_logger
    from cilantro.nodes import NodeFactory
    import os, time

    log = get_logger(__name__)

    m_info = TESTNET_MASTERNODES[0]
    m_info['ip'] = os.getenv('HOST_IP')

    mn = NodeFactory.run_masternode(ip=m_info['ip'], signing_key=m_info['sk'])

def run_witness(slot_num):
    from cilantro.logger import get_logger
    from cilantro.nodes import NodeFactory
    import os

    log = get_logger(__name__)

    w_info = TESTNET_WITNESSES[slot_num]
    w_info['ip'] = os.getenv('HOST_IP')

    NodeFactory.run_witness(ip=w_info['ip'], signing_key=w_info['sk'])


def run_delegate(slot_num):
    from cilantro.logger import get_logger
    from cilantro.nodes import NodeFactory
    import os

    log = get_logger("DELEGATE FACTORY")

    d_info = TESTNET_DELEGATES[slot_num]
    d_info['ip'] = os.getenv('HOST_IP')

    NodeFactory.run_delegate(ip=d_info['ip'], signing_key=d_info['sk'])

def run_mgmt():
    from cilantro.logger import get_logger
    from cilantro.utils.test import MPComposer

    log = get_logger(__name__)
    sk = TESTNET_MASTERNODES[0]['sk']
    vk = wallet.get_vk(sk)
    s,v = wallet.new()
    mpc = MPComposer(name='mgmt', sk=s)
    mpc.add_sub(filter='a', vk=vk)

class TestVKLookup(BaseNetworkTestCase):
    testname = 'vklookup'
    setuptime = 10
    compose_file = 'cilantro-bootstrap.yml'

    NUM_WITNESS = 2
    NUM_DELEGATES = 4

    @vmnet_test(run_webui=True)
    def test_vklookup(self):

        # Bootstrap master
        self.execute_python('masternode', run_mn, async=True)

        # Bootstrap witnesses
        for i, nodename in enumerate(self.groups['witness']):
            self.execute_python('witness_{}'.format(i+1+1), wrap_func(run_witness, i), async=True)

        # Bootstrap delegates
        for i, nodename in enumerate(self.groups['delegate']):
            self.execute_python('delegate_{}'.format(i+1+3), wrap_func(run_delegate, i), async=True)

        time.sleep(5)
        self.execute_python('mgmt', run_mgmt, async=True)

        input("Enter any key to terminate")

if __name__ == '__main__':
    unittest.main()
