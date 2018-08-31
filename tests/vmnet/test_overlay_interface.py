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
    from cilantro.protocol.overlay.interface import OverlayServer, OverlayClient
    from multiprocessing import Process
    import os, time

    log = get_logger(__name__)
    def event_handler(e):
        log.critical('{}: {}'.format(os.getenv('HOST_IP'), e))

    def server_proc():
        OverlayServer(sk=m_info['sk'])

    m_info = TESTNET_MASTERNODES[0]
    m_info['ip'] = os.getenv('HOST_IP')

    s = Process(target=server_proc)
    s.start()
    client = OverlayClient(event_handler, block=True)


def run_witness(slot_num):
    from cilantro.logger import get_logger
    from cilantro.protocol.overlay.interface import OverlayServer, OverlayClient
    from multiprocessing import Process
    import os

    log = get_logger(__name__)
    def event_handler(e):
        log.critical('{}: {}'.format(os.getenv('HOST_IP'), e))

    def server_proc():
        OverlayServer(sk=w_info['sk'])

    w_info = TESTNET_WITNESSES[slot_num]
    w_info['ip'] = os.getenv('HOST_IP')

    s = Process(target=server_proc)
    s.start()
    client = OverlayClient(event_handler, block=True)

def run_delegate(slot_num):
    from cilantro.logger import get_logger
    from cilantro.protocol.overlay.interface import OverlayServer, OverlayClient
    from multiprocessing import Process
    import os, asyncio

    log = get_logger("DELEGATE FACTORY")
    def event_handler(e):
        log.critical('{}: {}'.format(os.getenv('HOST_IP'), e))

    def server_proc():
        OverlayServer(sk=d_info['sk'])

    async def send_cmd(cli):
        await asyncio.sleep(15)
        cli.get_node_from_vk(d_info['vk'])

    d_info = TESTNET_DELEGATES[slot_num]
    d_info['ip'] = os.getenv('HOST_IP')

    s = Process(target=server_proc)
    s.start()
    client = OverlayClient(event_handler, block=False)
    asyncio.ensure_future(send_cmd(client))
    client.loop.run_forever()

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
