from vmnet.comm import file_listener
from vmnet.testcase import BaseTestCase
import unittest, time, random, vmnet, cilantro, asyncio, ujson as json
from os.path import join, dirname
from cilantro.utils.test.mp_test_case import vmnet_test, wrap_func
from cilantro.logger.base import get_logger

def masternode(idx):
    from cilantro.constants.testnet import TESTNET_MASTERNODES
    from cilantro.protocol.overlay.daemon import OverlayInterface
    from cilantro.constants.overlay_network import MIN_BOOTSTRAP_NODES
    from vmnet.comm import send_to_file
    import asyncio, json, os

    async def check():
        while True:
            await asyncio.sleep(1)
            if len(oi.neighbors) >= MIN_BOOTSTRAP_NODES:
                send_to_file(json.dumps({os.getenv('HOST_NAME'): True}))

    oi = OverlayInterface(TESTNET_MASTERNODES[idx]['sk'], block=False)
    oi.loop.run_until_complete(asyncio.gather(
        oi.tasks, check()
    ))

def witness(idx):
    from cilantro.constants.testnet import TESTNET_WITNESSES
    from cilantro.protocol.overlay.daemon import OverlayInterface
    from cilantro.constants.overlay_network import MIN_BOOTSTRAP_NODES
    from vmnet.comm import send_to_file
    import asyncio, json, os

    async def check():
        while True:
            await asyncio.sleep(1)
            if len(oi.neighbors) >= MIN_BOOTSTRAP_NODES:
                send_to_file(json.dumps({os.getenv('HOST_NAME'): True}))

    oi = OverlayInterface(TESTNET_WITNESSES[idx]['sk'], block=False)
    oi.loop.run_until_complete(asyncio.gather(
        oi.tasks, check()
    ))

def delegate(idx):
    from cilantro.constants.testnet import TESTNET_DELEGATES
    from cilantro.protocol.overlay.daemon import OverlayInterface
    from cilantro.constants.overlay_network import MIN_BOOTSTRAP_NODES
    from vmnet.comm import send_to_file
    import asyncio, json, os

    async def check():
        while True:
            await asyncio.sleep(1)
            if len(oi.neighbors) >= MIN_BOOTSTRAP_NODES:
                send_to_file(os.getenv('HOST_NAME'))

    oi = OverlayInterface(TESTNET_DELEGATES[idx]['sk'], block=False)
    oi.loop.run_until_complete(asyncio.gather(
        oi.tasks, check()
    ))

class TestInterface(BaseTestCase):

    log = get_logger(__name__)
    config_file = join(dirname(cilantro.__path__[0]), 'vmnet_configs', 'cilantro-2-4-4-bootstrap.json')

    def callback(self, data):
        for node in data:
            self.nodes_complete.add(node)

    def complete(self):
        all_nodes = set(self.groups['masternode']+self.groups['witness']+self.groups['delegate'])
        self.assertEqual(self.nodes_complete, all_nodes)

    def test_interface(self):
        self.nodes_complete = set()
        for idx, node in enumerate(self.groups['masternode']):
            self.execute_python(node, wrap_func(masternode, idx))
        for idx, node in enumerate(self.groups['witness']):
            self.execute_python(node, wrap_func(witness, idx))
        for idx, node in enumerate(self.groups['delegate']):
            self.execute_python(node, wrap_func(delegate, idx))

        file_listener(self, self.callback, self.complete, 10)

if __name__ == '__main__':
    unittest.main()
