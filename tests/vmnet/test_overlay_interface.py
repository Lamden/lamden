from vmnet.testcase import BaseNetworkTestCase
import unittest, time, random, os
from cilantro.protocol import wallet
from cilantro.constants.testnet import TESTNET_MASTERNODES, TESTNET_WITNESSES, TESTNET_DELEGATES
from cilantro.utils.test.mp_test_case import vmnet_test

import vmnet

def wrap_func(fn, *args, **kwargs):
    def wrapper():
        return fn(*args, **kwargs)
    return wrapper

def run_mn():
    from cilantro.logger import get_logger
    from cilantro.protocol.overlay.interface import OverlayInterface
    import os, time

    log = get_logger(__name__)
    def event_handler(e):
        log.critical('{}: {}'.format(os.getenv('HOST_IP'), e))

    m_info = TESTNET_MASTERNODES[0]
    m_info['ip'] = os.getenv('HOST_IP')

    OverlayInterface._start_service(sk=m_info['sk'])
    OverlayInterface.listen_for_events(event_handler)

def run_witness(slot_num):
    from cilantro.logger import get_logger
    from cilantro.protocol.overlay.interface import OverlayInterface
    import os

    log = get_logger(__name__)
    def event_handler(e):
        log.critical('{}: {}'.format(os.getenv('HOST_IP'), e))

    w_info = TESTNET_WITNESSES[slot_num]
    w_info['ip'] = os.getenv('HOST_IP')

    OverlayInterface._start_service(sk=w_info['sk'])
    OverlayInterface.listen_for_events(event_handler)


def run_delegate(slot_num):
    from cilantro.logger import get_logger
    from cilantro.protocol.overlay.interface import OverlayInterface
    import os

    log = get_logger("DELEGATE FACTORY")
    def event_handler(e):
        log.critical('{}: {}'.format(os.getenv('HOST_IP'), e))

    d_info = TESTNET_DELEGATES[slot_num]
    d_info['ip'] = os.getenv('HOST_IP')

    OverlayInterface._start_service(sk=d_info['sk'])
    OverlayInterface.listen_for_events(event_handler)

class TestOverlayInterface(BaseNetworkTestCase):
    config_file = '../../vmnet_configs/cilantro-bootstrap.json'

    NUM_WITNESS = 2
    NUM_DELEGATES = 4

    @vmnet_test(run_webui=True)
    def test_vklookup(self):

        # Bootstrap master
        self.execute_python('masternode', run_mn)

        # Bootstrap witnesses
        for i, nodename in enumerate(self.groups['witness']):
            self.execute_python(nodename, wrap_func(run_witness, i))

        # Bootstrap delegates
        for i, nodename in enumerate(self.groups['delegate']):
            self.execute_python(nodename, wrap_func(run_delegate, i))

        time.sleep(25)
        for i, nodename in enumerate(self.groups['witness'] + self.groups['delegate']):
            os.system('docker kill {}'.format(nodename))
            time.sleep(1)

        input("Enter any key to terminate")

if __name__ == '__main__':
    unittest.main()
