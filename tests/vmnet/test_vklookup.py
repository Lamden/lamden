from vmnet.test.base import *
import unittest, time, random

import vmnet

def wrap_func(fn, *args, **kwargs):
    def wrapper():
        return fn(*args, **kwargs)
    return wrapper

def run_mn():
    from cilantro.logger import get_logger
    from cilantro import Constants
    from cilantro.nodes import NodeFactory
    from cilantro.db import DB, DB_NAME
    import os, time

    log = get_logger(__name__)

    m_info = Constants.Testnet.Masternodes[0]
    m_info['ip'] = os.getenv('HOST_IP')

    mn = NodeFactory.run_masternode(ip=m_info['ip'], signing_key=m_info['sk'])

def run_witness(slot_num):
    from cilantro.logger import get_logger
    from cilantro import Constants
    from cilantro.nodes import NodeFactory
    from cilantro.db import DB, DB_NAME
    import os

    log = get_logger(__name__)

    w_info = Constants.Testnet.Witnesses[slot_num]
    w_info['ip'] = os.getenv('HOST_IP')

    NodeFactory.run_witness(ip=w_info['ip'], signing_key=w_info['sk'])


def run_delegate(slot_num):
    from cilantro.logger import get_logger
    from cilantro import Constants
    from cilantro.nodes import NodeFactory
    from cilantro.db import DB, DB_NAME
    import os

    log = get_logger("DELEGATE FACTORY")

    d_info = Constants.Testnet.Delegates[slot_num]
    d_info['ip'] = os.getenv('HOST_IP')

    NodeFactory.run_delegate(ip=d_info['ip'], signing_key=d_info['sk'])

def run_mgmt():
    from cilantro.logger import get_logger
    from cilantro import Constants
    from cilantro.db import DB, DB_NAME
    from cilantro.utils.test import MPComposer
    from cilantro.protocol.wallets import ED25519Wallet
    import os, time, asyncio

    log = get_logger(__name__)
    sk = Constants.Testnet.Masternodes[0]['sk']
    vk = Constants.Protocol.Wallets.get_vk(sk)
    s,v = ED25519Wallet.new()
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
