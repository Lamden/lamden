from vmnet.testcase import BaseTestCase
from vmnet.comm import file_listener
import unittest, time, random, vmnet, cilantro, asyncio, ujson as json, os
from os.path import join, dirname
from cilantro.utils.test.mp_test_case import vmnet_test, wrap_func
from cilantro.logger.base import get_logger

def run_node(node_type, idx):
    from vmnet.comm import send_to_file
    from cilantro.protocol.overlay.discovery import Discovery
    from cilantro.constants.overlay_network import MIN_DISCOVERY_NODES
    from cilantro.protocol.overlay.auth import Auth # TODO: replace with utils
    import asyncio, os, ujson as json
    from os import getenv as env
    from cilantro.storage.vkbook import VKBook
    VKBook.setup()
    async def check_nodes():
        while True:
            await asyncio.sleep(1)
            if len(Discovery.discovered_nodes) >= MIN_DISCOVERY_NODES:
                send_to_file(env('HOST_NAME'))

    from cilantro.logger import get_logger
    log = get_logger('{}_{}'.format(node_type, idx))
    loop = asyncio.get_event_loop()
    Auth.setup(VKBook.constitution[node_type][idx]['sk'])
    Discovery.setup() # TODO: remove when re-architected
    log.test('Starting {}_{}'.format(node_type, idx))
    tasks = asyncio.ensure_future(asyncio.gather(
        Discovery.listen(),
        Discovery.discover_nodes(env('HOST_IP')),
        check_nodes()
    ))
    loop.run_until_complete(tasks)

class TestDiscovery(BaseTestCase):
    log = get_logger(__name__)
    config_file = join(dirname(cilantro.__path__[0]), 'vmnet_configs', 'cilantro-nodes-4.json')
    environment = {'CONSTITUTION_FILE': '2-2-2.json'}
    enable_ui = False

################################################################################
#   Test Setup
################################################################################

    def setUp(self):
        super().setUp()
        self.all_nodes = set(self.groups['node'])
        self.nodes_complete = set()

    def tearDown(self):
        file_listener(self, self.callback, self.timeout, 60)
        super().tearDown()

    def success(self):
        self.log.success('=' * 128)
        self.log.success('\t{} SUCCEEDED\t\t'.format(self.id()))
        self.log.success('=' * 128)

    def callback(self, data):
        for node in data:
            self.nodes_complete.add(node)
        if self.nodes_complete == self.all_nodes:
            self.success()
            self.end_test()

    def timeout(self):
        self.assertEqual(self.nodes_complete, self.all_nodes)

################################################################################
#   Tests
################################################################################

    def test_regular_all_masters(self):
        self.execute_python('node_1', wrap_func(run_node, 'masternodes', 0))
        self.execute_python('node_2', wrap_func(run_node, 'masternodes', 1))
        self.execute_python('node_3', wrap_func(run_node, 'delegates', 0))
        self.execute_python('node_4', wrap_func(run_node, 'delegates', 1))

    def test_regular_one_master(self):
        self.all_nodes.remove('node_2')
        self.execute_python('node_1', wrap_func(run_node, 'masternodes', 0))
        self.execute_python('node_3', wrap_func(run_node, 'delegates', 0))
        self.execute_python('node_4', wrap_func(run_node, 'delegates', 1))

    def test_late_delegate(self):
        self.execute_python('node_1', wrap_func(run_node, 'masternodes', 0))
        self.execute_python('node_2', wrap_func(run_node, 'masternodes', 1))
        self.execute_python('node_3', wrap_func(run_node, 'delegates', 0))
        self.log.test('Waiting 10 seconds before spinning up last node')
        time.sleep(10)
        self.execute_python('node_4', wrap_func(run_node, 'delegates', 1))

    def test_one_master_late_delegate(self):
        self.all_nodes.remove('node_2')
        self.execute_python('node_1', wrap_func(run_node, 'masternodes', 0))
        self.execute_python('node_3', wrap_func(run_node, 'delegates', 0))
        self.log.test('Waiting 10 seconds before spinning up last node')
        time.sleep(10)
        self.execute_python('node_4', wrap_func(run_node, 'delegates', 1))

    def test_one_master_down_up(self):
        self.all_nodes.remove('node_2')
        self.execute_python('node_1', wrap_func(run_node, 'masternodes', 0))
        self.execute_python('node_3', wrap_func(run_node, 'delegates', 0))
        self.kill_node('node_1')
        self.execute_python('node_4', wrap_func(run_node, 'delegates', 1))
        self.log.test('Waiting 10 seconds before spinning up master node again')
        time.sleep(10)
        self.start_node('node_1')
        self.rerun_node_script('node_1')

    def test_one_late_masternode(self):
        self.all_nodes.remove('node_2')
        self.execute_python('node_3', wrap_func(run_node, 'delegates', 0))
        self.execute_python('node_4', wrap_func(run_node, 'delegates', 1))
        self.log.test('Waiting 10 seconds before spinning up master node')
        time.sleep(10)
        self.execute_python('node_1', wrap_func(run_node, 'masternodes', 0))

if __name__ == '__main__':
    unittest.main()
