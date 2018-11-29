from vmnet.testcase import BaseTestCase
from vmnet.comm import file_listener
import unittest, time, random, vmnet, cilantro, asyncio, ujson as json
from os.path import join, dirname
from cilantro.utils.test.mp_test_case import vmnet_test, wrap_func
from cilantro.logger.base import get_logger
from cilantro.constants.test_suites import CI_FACTOR

def masternode(idx):
    from vmnet.comm import send_to_file
    from cilantro.constants.testnet import TESTNET_MASTERNODES
    from cilantro.protocol.overlay.discovery import Discovery
    from cilantro.protocol.overlay.auth import Auth
    import asyncio, os, ujson as json

    async def check_nodes():
        while True:
            await asyncio.sleep(1)
            if len(Discovery.discovered_nodes) >= 1:
                send_to_file(os.getenv('HOST_NAME'))

    from cilantro.logger import get_logger
    log = get_logger('MasterNode_{}'.format(idx))
    loop = asyncio.get_event_loop()
    Auth.setup(TESTNET_MASTERNODES[idx]['sk'])
    Discovery.setup()
    tasks = asyncio.ensure_future(asyncio.gather(
        Discovery.listen(),
        Discovery.discover_nodes(os.getenv('HOST_IP')),
        check_nodes()
    ))
    loop.run_until_complete(tasks)


def witness(idx):
    from vmnet.comm import send_to_file
    from cilantro.constants.testnet import TESTNET_WITNESSES
    from cilantro.protocol.overlay.discovery import Discovery
    from cilantro.protocol.overlay.auth import Auth
    from cilantro.constants.overlay_network import MIN_BOOTSTRAP_NODES
    import asyncio, os, ujson as json

    async def check_nodes():
        while True:
            await asyncio.sleep(1)
            if len(Discovery.discovered_nodes) >= MIN_BOOTSTRAP_NODES:
                send_to_file(os.getenv('HOST_NAME'))

    from cilantro.logger import get_logger
    log = get_logger('Witness_{}'.format(idx))
    loop = asyncio.get_event_loop()
    Auth.setup(TESTNET_WITNESSES[idx]['sk'])
    Discovery.setup()
    tasks = asyncio.ensure_future(asyncio.gather(
        Discovery.listen(),
        Discovery.discover_nodes(os.getenv('HOST_IP')),
        check_nodes()
    ))
    loop.run_until_complete(tasks)


def delegate(idx):
    from vmnet.comm import send_to_file
    from cilantro.constants.testnet import TESTNET_DELEGATES
    from cilantro.protocol.overlay.discovery import Discovery
    from cilantro.protocol.overlay.auth import Auth
    from cilantro.constants.overlay_network import MIN_BOOTSTRAP_NODES
    import asyncio, os, ujson as json

    async def check_nodes():
        while True:
            await asyncio.sleep(1)
            if len(Discovery.discovered_nodes) >= MIN_BOOTSTRAP_NODES:
                send_to_file(os.getenv('HOST_NAME'))

    from cilantro.logger import get_logger
    log = get_logger('Delegate_{}'.format(idx))
    loop = asyncio.get_event_loop()
    Auth.setup(TESTNET_DELEGATES[idx]['sk'])
    Discovery.setup()
    tasks = asyncio.ensure_future(asyncio.gather(
        Discovery.listen(),
        Discovery.discover_nodes(os.getenv('HOST_IP')),
        check_nodes()
    ))
    loop.run_until_complete(tasks)


class TestDiscovery(BaseTestCase):
    log = get_logger(__name__)
    config_file = join(dirname(cilantro.__path__[0]), 'vmnet_configs', 'cilantro-2-2-4-bootstrap.json')
    enable_ui = False

    def callback(self, data):
        for node in data:
            self.nodes_complete.add(node)
        if self.nodes_complete == self.all_nodes:
            self.end_test()

    def timeout(self):
        self.assertEqual(self.nodes_complete, self.all_nodes)

    def test_discovery(self):
        self.all_nodes = set(self.groups['masternode'] + self.groups['witness'] + self.groups['delegate'])
        self.nodes_complete = set()
        for idx, node in enumerate(self.groups['masternode']):
            self.execute_python(node, wrap_func(masternode, idx))
        for idx, node in enumerate(self.groups['witness']):
            self.execute_python(node, wrap_func(witness, idx))
        for idx, node in enumerate(self.groups['delegate']):
            self.execute_python(node, wrap_func(delegate, idx))
        time.sleep(15*CI_FACTOR)
        file_listener(self, self.callback, self.timeout, 30)


if __name__ == '__main__':
    unittest.main()
