from vmnet.testcase import BaseTestCase
from vmnet.comm import file_listener
import unittest, time, random, vmnet, cilantro, asyncio, ujson as json, os
from os.path import join, dirname
from cilantro.utils.test.mp_test_case import vmnet_test, wrap_func
from cilantro.logger.base import get_logger


def run_node(node_type, idx, change_constants=False, fail=False):
    if change_constants:
        from unittest.mock import MagicMock, patch
        patch("cilantro.protocol.overlay.discovery.DISCOVERY_RETRIES_BEFORE_SOLO_BOOT", 2).start()
        patch("cilantro.protocol.overlay.discovery.DISCOVERY_WAIT", 2).start()
        patch("cilantro.protocol.overlay.discovery.DISCOVERY_RETRIES", 1).start()
        patch("cilantro.protocol.overlay.discovery.DISCOVERY_LONG_WAIT", 4).start()
        patch("cilantro.protocol.overlay.discovery.DISCOVERY_ITER", 3).start()

    from vmnet.comm import send_to_file
    from cilantro.protocol.overlay.discovery import Discovery
    from cilantro.utils.keys import Keys
    import asyncio, os, ujson as json, zmq.asyncio
    from os import getenv as env
    from cilantro.storage.vkbook import VKBook
    VKBook.setup()
    async def check_nodes():
        while True:
            await asyncio.sleep(1)
            if discover_fut.done():
                send_to_file(env('HOST_NAME'))
    from cilantro.logger import get_logger
    log = get_logger('{}_{}'.format(node_type, idx))
    loop = asyncio.get_event_loop()
    ctx = zmq.asyncio.Context()
    creds = VKBook.constitution[node_type][idx]
    Keys.setup(creds['sk'])
    discovery = Discovery(Keys.vk, ctx) # TODO: remove when re-architected
    discover_fut = asyncio.ensure_future(discovery.discover_nodes())
    log.test('Starting {}_{}'.format(node_type, idx))
    tasks = asyncio.ensure_future(asyncio.gather(
        discovery.listen(),
        discover_fut,
        check_nodes()
    ))
    if fail:
        try:
            loop.run_until_complete(tasks)
        except:
            send_to_file(env('HOST_NAME'))
    else:
        loop.run_until_complete(tasks)

class TestDiscovery(BaseTestCase):
    log = get_logger(__name__)
    config_file = join(dirname(cilantro.__path__[0]), 'vmnet_configs', 'cilantro-nodes-4.json')
    environment = {'CONSTITUTION_FILE': '2-2-2.json'}
    enable_ui = False

    def setUp(self):
        super().setUp()
        self.all_nodes = set(self.groups['node'])
        self.nodes_complete = set()

    def success(self):
        self.log.success('=' * 128)
        self.log.success('\t{} SUCCEEDED\t\t'.format(self.id()))
        self.log.success('=' * 128)

class TestDiscoverySuccess(TestDiscovery):
    log = get_logger(__name__)
    config_file = join(dirname(cilantro.__path__[0]), 'vmnet_configs', 'cilantro-nodes-4.json')
    environment = {'CONSTITUTION_FILE': '2-2-2.json'}
    enable_ui = False

################################################################################
#   Test Setup
################################################################################

    def tearDown(self):
        file_listener(self, self.callback, self.timeout, 60)
        super().tearDown()

    def callback(self, data):
        fut.result() # Makes sure no exception had been raised
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


class TestDiscoveryFail(TestDiscovery):
    log = get_logger(__name__)
    config_file = join(dirname(cilantro.__path__[0]), 'vmnet_configs', 'cilantro-nodes-4.json')
    environment = {'CONSTITUTION_FILE': '2-2-2.json'}
    enable_ui = False

################################################################################
#   Test Setup
################################################################################

    def callback(self, data):
        for node in data:
            self.nodes_complete.add(node)

    def timeout(self):
        self.assertEqual(len(self.nodes_complete), 0)
        self.success()
        self.end_test()

################################################################################
#   Tests
################################################################################

    def test_no_masternodes(self):
        self.execute_python('node_3', wrap_func(run_node, 'delegates', 0))
        self.execute_python('node_4', wrap_func(run_node, 'delegates', 1))
        file_listener(self, self.callback, self.timeout, 15)

    def test_failed_discovery(self):
        def _timeout():
            self.assertEqual(set(self.nodes_complete), set(['node_3', 'node_4']))
            self.success()
            self.end_test()
        self.timeout = _timeout
        self.execute_python('node_3', wrap_func(run_node, 'delegates', 0, change_constants=True, fail=True))
        self.execute_python('node_4', wrap_func(run_node, 'delegates', 1, change_constants=True, fail=True))
        file_listener(self, self.callback, self.timeout, 15)

if __name__ == '__main__':
    unittest.main()
