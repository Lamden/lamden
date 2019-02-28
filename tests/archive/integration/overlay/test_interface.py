from vmnet.comm import file_listener
from vmnet.testcase import BaseTestCase
import unittest, time, random, vmnet, cilantro_ee, asyncio, ujson as json
from os.path import join, dirname
from cilantro_ee.utils.test.mp_test_case import vmnet_test, wrap_func
from cilantro_ee.logger.base import get_logger


def masternode(idx):
    from cilantro_ee.constants.testnet import TESTNET_MASTERNODES
    from cilantro_ee.protocol.overlay.interface import OverlayInterface
    from cilantro_ee.constants.overlay_network import MIN_BOOTSTRAP_NODES
    from vmnet.comm import send_to_file
    import asyncio, json, os

    async def check():
        while True:
            await asyncio.sleep(1)
            if len(oi.neighbors) >= MIN_BOOTSTRAP_NODES:
                send_to_file(os.getenv('HOST_NAME'))

    oi = OverlayInterface(TESTNET_MASTERNODES[idx]['sk'])
    oi.tasks.append(check())
    oi.start()


def witness(idx):
    from cilantro_ee.constants.testnet import TESTNET_WITNESSES
    from cilantro_ee.protocol.overlay.interface import OverlayInterface
    from cilantro_ee.constants.overlay_network import MIN_BOOTSTRAP_NODES
    from vmnet.comm import send_to_file
    import asyncio, json, os

    async def check():
        while True:
            await asyncio.sleep(1)
            if len(oi.neighbors) >= MIN_BOOTSTRAP_NODES:
                send_to_file(os.getenv('HOST_NAME'))

    oi = OverlayInterface(TESTNET_WITNESSES[idx]['sk'])
    oi.tasks.append(check())
    oi.start()


def delegate(idx):
    from cilantro_ee.constants.testnet import TESTNET_DELEGATES
    from cilantro_ee.protocol.overlay.interface import OverlayInterface
    from cilantro_ee.constants.overlay_network import MIN_BOOTSTRAP_NODES
    from vmnet.comm import send_to_file
    import asyncio, json, os

    async def check():
        while True:
            await asyncio.sleep(1)
            if len(oi.neighbors) >= MIN_BOOTSTRAP_NODES:
                send_to_file(os.getenv('HOST_NAME'))

    oi = OverlayInterface(TESTNET_DELEGATES[idx]['sk'])
    oi.tasks.append(check())
    oi.start()


class TestInterface(BaseTestCase):
    log = get_logger(__name__)
    config_file = join(dirname(cilantro_ee.__path__[0]), 'vmnet_configs', 'cilantro_ee-2-2-4-bootstrap.json')
    enable_ui = False

    def callback(self, data):
        for node in data:
            self.nodes_complete.add(node)
        if self.nodes_complete == self.all_nodes:
            self.end_test()

    def timeout(self):
        self.assertEqual(self.nodes_complete, self.all_nodes)

    def test_interface(self):
        self.all_nodes = set(self.groups['masternode'] + self.groups['witness'] + self.groups['delegate'])
        self.nodes_complete = set()
        for idx, node in enumerate(self.groups['masternode']):
            self.execute_python(node, wrap_func(masternode, idx))
        for idx, node in enumerate(self.groups['witness']):
            self.execute_python(node, wrap_func(witness, idx))
        for idx, node in enumerate(self.groups['delegate']):
            self.execute_python(node, wrap_func(delegate, idx))

        file_listener(self, self.callback, self.timeout, 30)


if __name__ == '__main__':
    unittest.main()
