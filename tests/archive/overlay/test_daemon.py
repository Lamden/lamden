from vmnet.testcase import BaseTestCase
from cilantro_ee.protocol.overlay.kademlia.node import Node
from vmnet.comm import file_listener
import unittest, time, random, vmnet, cilantro_ee, asyncio, ujson as json, os
from os.path import join, dirname
from cilantro_ee.utils.test.mp_test_case import vmnet_test, wrap_func
from cilantro_ee.protocol.overlay.kademlia.utils import digest
from cilantro_ee.logger.base import get_logger
from cilantro_ee.constants.test_suites import CI_FACTOR
from cilantro_ee.constants.overlay_network import *
from cilantro_ee.storage.vkbook import VKBook
from cilantro_ee.constants.ports import DHT_PORT
import time

def run_node(node_type, idx, use_ips=None):

    from vmnet.comm import send_to_file
    from cilantro_ee.utils.lprocess import LProcess
    from cilantro_ee.protocol.overlay.daemon import OverlayServer, OverlayClient
    from cilantro_ee.constants.overlay_network import MIN_BOOTSTRAP_NODES
    from cilantro_ee.protocol.overlay.kademlia.utils import digest
    from cilantro_ee.constants.ports import DHT_PORT
    from cilantro_ee.protocol.overlay.auth import Auth
    import asyncio, os, ujson as json, zmq.asyncio
    from cilantro_ee.storage.vkbook import VKBook
    VKBook.setup()

    def received_event(e):
        name = os.getenv('HOST_NAME')
        if e.get('status') == 'ready':
            log.debug('<test>: node {} got event ready'.format(name))
            send_to_file(name)

    from cilantro_ee.logger import get_logger
    log = get_logger('{}_{}'.format(node_type.upper(), idx))
    loop = asyncio.get_event_loop()
    ctx = zmq.asyncio.Context()
    creds = VKBook.constitution[node_type][idx]
    overlay_proc = LProcess(target=OverlayServer, args=(creds['sk'],))
    overlay_proc.start()
    client = OverlayClient(received_event, loop, ctx, start=True)

class TestDaemon(BaseTestCase):
    log = get_logger(__name__)
    config_file = join(dirname(cilantro_ee.__path__[0]), 'vmnet_configs', 'cilantro_ee-nodes-6.json')
    environment = {'CONSTITUTION_FILE': '2-2-2.json'}
    enable_ui = False
    timeout_delay = 30

    def callback(self, data):
        self.nodes_complete = self.nodes_complete.union(data)
        if self.succeeded():
            self._success_msg()
            self.end_test()

    def _success_msg(self):
        self.log.success('=' * 128)
        self.log.success('\t{} SUCCEEDED\t\t'.format(self.id()))
        self.log.success('=' * 128)

    def succeeded(self):
        return set(self.ns) == self.nodes_complete

    def timeout(self):
        self.assertTrue(self.succeeded())
        self._success_msg()

    def setUp(self):
        super().setUp()
        self.all_nodes = set(self.groups['node'])
        self.ns = self.groups['node']
        self.nodes_complete = set()

    def test_daemon_connectivity(self):

        self.execute_python(self.ns[2], wrap_func(run_node, 'delegates', 0))
        self.execute_python(self.ns[3], wrap_func(run_node, 'delegates', 1))
        self.execute_python(self.ns[4], wrap_func(run_node, 'witnesses', 0))
        self.execute_python(self.ns[5], wrap_func(run_node, 'witnesses', 1))

        time.sleep(10)
        self.execute_python(self.ns[0], wrap_func(run_node, 'masternodes', 0))
        time.sleep(10)
        self.execute_python(self.ns[1], wrap_func(run_node, 'masternodes', 1))

        file_listener(self, self.callback, self.timeout, self.timeout_delay)

if __name__ == '__main__':
    unittest.main()
