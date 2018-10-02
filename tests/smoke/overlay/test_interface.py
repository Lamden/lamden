from vmnet.testcase import BaseTestCase
from vmnet.comm import file_listener
import unittest, time, random, vmnet, cilantro, asyncio, ujson as json
from os.path import join, dirname
from cilantro.utils.test.mp_test_case import vmnet_test, wrap_func
from cilantro.logger.base import get_logger

def masternode(idx):
    from vmnet.comm import send_to_file
    from cilantro.constants.testnet import TESTNET_MASTERNODES
    from cilantro.protocol.overlay.interface import OverlayInterface

    async def check_nodes():
        while True:
            await asyncio.sleep(1)

    oi = OverlayInterface(TESTNET_MASTERNODES[idx]['sk'])

def witness(idx):
    from vmnet.comm import send_to_file
    from cilantro.constants.testnet import TESTNET_WITNESSES
    from cilantro.protocol.overlay.interface import OverlayInterface

    async def check_nodes():
        while True:
            await asyncio.sleep(1)

    oi = OverlayInterface(TESTNET_WITNESSES[idx]['sk'])

def delegate(idx):
    from vmnet.comm import send_to_file
    from cilantro.constants.testnet import TESTNET_DELEGATES
    from cilantro.protocol.overlay.interface import OverlayInterface

    async def check_nodes():
        while True:
            await asyncio.sleep(1)

    oi = OverlayInterface(TESTNET_DELEGATES[idx]['sk'])

class TestInterface(BaseTestCase):

    log = get_logger(__name__)
    config_file = join(dirname(cilantro.__path__[0]), 'vmnet_configs', 'cilantro-2-4-4-bootstrap.json')

    def callback(self, data):
        pass

    def complete(self):
        pass

    def test_interface(self):
        self.nodes_complete = {}
        for idx, node in enumerate(self.groups['masternode']):
            self.execute_python(node, wrap_func(masternode, idx))
        for idx, node in enumerate(self.groups['witness']):
            self.execute_python(node, wrap_func(witness, idx))
        for idx, node in enumerate(self.groups['delegate']):
            self.execute_python(node, wrap_func(delegate, idx))

        file_listener(self, self.callback, self.complete, 30)

        input("Press any key to terminate")

if __name__ == '__main__':
    unittest.main()
