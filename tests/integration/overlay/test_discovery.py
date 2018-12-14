from vmnet.testcase import BaseTestCase
from vmnet.comm import file_listener
import unittest, time, random, vmnet, cilantro, asyncio, ujson as json, os
from os.path import join, dirname
from cilantro.utils.test.mp_test_case import vmnet_test, wrap_func
from cilantro.logger.base import get_logger
from cilantro.constants.test_suites import CI_FACTOR

def masternode(idx):
    from vmnet.comm import send_to_file
    from cilantro.protocol.overlay.discovery import Discovery
    from cilantro.protocol.overlay.auth import Auth
    import asyncio, os, ujson as json
    from cilantro.storage.vkbook import VKBook
    VKBook.setup()

    async def check_nodes():
        while True:
            await asyncio.sleep(1)
            if len(Discovery.discovered_nodes) >= 1:
                send_to_file(os.getenv('HOST_NAME'))

    from cilantro.logger import get_logger
    log = get_logger('MasterNode_{}'.format(idx))
    loop = asyncio.get_event_loop()
    Auth.setup(VKBook.constitution['masternodes'][idx]['sk'])
    Discovery.setup()
    tasks = asyncio.ensure_future(asyncio.gather(
        Discovery.listen(),
        Discovery.discover_nodes(os.getenv('HOST_IP')),
        check_nodes()
    ))
    loop.run_until_complete(tasks)


def delegates(idx):
    from vmnet.comm import send_to_file
    from cilantro.protocol.overlay.discovery import Discovery
    from cilantro.protocol.overlay.auth import Auth
    from cilantro.constants.overlay_network import MIN_BOOTSTRAP_NODES
    import asyncio, os, ujson as json
    from cilantro.storage.vkbook import VKBook
    VKBook.setup()

    async def check_nodes():
        while True:
            await asyncio.sleep(1)
            if len(Discovery.discovered_nodes) >= MIN_BOOTSTRAP_NODES:
                send_to_file(os.getenv('HOST_NAME'))

    from cilantro.logger import get_logger
    log = get_logger('Node_{}'.format(idx))
    loop = asyncio.get_event_loop()
    Auth.setup(VKBook.constitution['delegates'][idx]['sk'])
    Discovery.setup()
    tasks = asyncio.ensure_future(asyncio.gather(
        Discovery.listen(),
        Discovery.discover_nodes(os.getenv('HOST_IP')),
        check_nodes()
    ))
    loop.run_until_complete(tasks)


class TestDiscovery(BaseTestCase):
    log = get_logger(__name__)
    config_file = join(dirname(cilantro.__path__[0]), 'vmnet_configs', 'cilantro-nodes-4.json')
    environment = {'CONSTITUTION_FILE': '2-2-2.json'}
    enable_ui = False

    def callback(self, data):
        for node in data:
            self.nodes_complete.add(node)
        if self.nodes_complete == self.all_nodes:
            self.end_test()

    def timeout(self):
        self.assertEqual(self.nodes_complete, self.all_nodes)

    def test_discovery(self):
        self.all_nodes = set(self.groups['node'])
        self.nodes_complete = set()
        self.execute_python(self.groups['node'][0], wrap_func(masternode, 0))
        self.execute_python(self.groups['node'][1], wrap_func(masternode, 1))
        for idx, node in enumerate(self.groups['node'][2:]):
            self.execute_python(node, wrap_func(delegates, idx))

        # input("Press key to restart node_1")
        # self.log.important3("Restarting node_1 in 5s...")
        # self.restart_node('node_1', dead_time=5)

        time.sleep(15*CI_FACTOR)

        file_listener(self, self.callback, self.timeout, 3600)


if __name__ == '__main__':
    unittest.main()
