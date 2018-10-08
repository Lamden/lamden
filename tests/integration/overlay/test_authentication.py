from vmnet.comm import file_listener
from vmnet.testcase import BaseTestCase
import unittest, time, random, vmnet, cilantro, asyncio, ujson as json
from os.path import join, dirname
from cilantro.utils.test.mp_test_case import vmnet_test, wrap_func
from cilantro.logger.base import get_logger

def masternode(idx, node_count):
    from cilantro.constants.testnet import TESTNET_MASTERNODES, TESTNET_WITNESSES, TESTNET_DELEGATES
    from cilantro.protocol.overlay.interface import OverlayInterface
    from cilantro.constants.overlay_network import MIN_BOOTSTRAP_NODES
    from vmnet.comm import send_to_file
    import asyncio, json, os
    from cilantro.logger import get_logger
    log = get_logger('MasterNode_{}'.format(idx))

    async def check():
        while True:
            await asyncio.sleep(1)
            if len(oi.authorized_nodes['*']) >= node_count:
                send_to_file(os.getenv('HOST_NAME'))

    async def connect():
        await asyncio.sleep(10)
        await asyncio.gather(*[oi.authenticate(vk) for vk in all_nodes])

    masternodes = [node['vk'] for node in TESTNET_MASTERNODES]
    witnesses = [node['vk'] for node in TESTNET_WITNESSES]
    delegates = [node['vk'] for node in TESTNET_DELEGATES]
    all_nodes = masternodes + witnesses + delegates

    oi = OverlayInterface(TESTNET_MASTERNODES[idx]['sk'])
    oi.tasks += [connect(), check()]
    oi.start()

def witness(idx, node_count):
    from cilantro.constants.testnet import TESTNET_MASTERNODES, TESTNET_WITNESSES, TESTNET_DELEGATES
    from cilantro.protocol.overlay.interface import OverlayInterface
    from cilantro.constants.overlay_network import MIN_BOOTSTRAP_NODES
    from vmnet.comm import send_to_file
    import asyncio, json, os
    from cilantro.logger import get_logger
    log = get_logger('WitnessNode_{}'.format(idx))

    async def check():
        while True:
            await asyncio.sleep(1)
            if len(oi.authorized_nodes['*']) >= node_count:
                send_to_file(os.getenv('HOST_NAME'))

    async def connect():
        await asyncio.sleep(10)
        await asyncio.gather(*[oi.authenticate(vk) for vk in all_nodes])

    masternodes = [node['vk'] for node in TESTNET_MASTERNODES]
    witnesses = [node['vk'] for node in TESTNET_WITNESSES]
    delegates = [node['vk'] for node in TESTNET_DELEGATES]
    all_nodes = masternodes + witnesses + delegates

    oi = OverlayInterface(TESTNET_WITNESSES[idx]['sk'])
    oi.tasks += [connect(), check()]
    oi.start()

def delegate(idx, node_count):
    from cilantro.constants.testnet import TESTNET_MASTERNODES, TESTNET_WITNESSES, TESTNET_DELEGATES
    from cilantro.protocol.overlay.interface import OverlayInterface
    from cilantro.constants.overlay_network import MIN_BOOTSTRAP_NODES
    from vmnet.comm import send_to_file
    import asyncio, json, os
    from cilantro.logger import get_logger
    log = get_logger('DelegateNode_{}'.format(idx))

    async def check():
        while True:
            await asyncio.sleep(1)
            if len(oi.authorized_nodes['*']) >= node_count:
                send_to_file(os.getenv('HOST_NAME'))

    async def connect():
        await asyncio.sleep(10)
        await asyncio.gather(*[oi.authenticate(vk) for vk in all_nodes])

    masternodes = [node['vk'] for node in TESTNET_MASTERNODES]
    witnesses = [node['vk'] for node in TESTNET_WITNESSES]
    delegates = [node['vk'] for node in TESTNET_DELEGATES]
    all_nodes = masternodes + witnesses + delegates

    oi = OverlayInterface(TESTNET_DELEGATES[idx]['sk'])
    oi.tasks += [connect(), check()]
    oi.start()

class TestAuthentication(BaseTestCase):

    log = get_logger(__name__)
    config_file = join(dirname(cilantro.__path__[0]), 'vmnet_configs', 'cilantro-2-2-4-bootstrap.json')

    def callback(self, data):
        for node in data:
            self.nodes_complete.add(node)

    def complete(self):
        all_nodes = set(self.groups['masternode']+self.groups['witness']+self.groups['delegate'])
        self.assertEqual(self.nodes_complete, all_nodes)

    def test_authentication(self):
        node_count = len(self.groups['masternode']+self.groups['witness']+self.groups['delegate'])
        self.nodes_complete = set()
        for idx, node in enumerate(self.groups['masternode']):
            self.execute_python(node, wrap_func(masternode, idx, node_count))
        for idx, node in enumerate(self.groups['witness']):
            self.execute_python(node, wrap_func(witness, idx, node_count))
        for idx, node in enumerate(self.groups['delegate']):
            self.execute_python(node, wrap_func(delegate, idx, node_count))

        file_listener(self, self.callback, self.complete, 30)

if __name__ == '__main__':
    unittest.main()
