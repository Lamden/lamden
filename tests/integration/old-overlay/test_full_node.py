# from vmnet.testcase import BaseTestCase
# from cilantro.protocol.overlay.kademlia.node import Node
# from vmnet.comm import file_listener
# import unittest, time, random, vmnet, cilantro, asyncio, ujson as json, os
# from os.path import join, dirname
# from cilantro.utils.test.mp_test_case import vmnet_test, wrap_func
# from cilantro.protocol.overlay.kademlia.utils import digest
# from cilantro.logger.base import get_logger
# from cilantro.constants.test_suites import CI_FACTOR
# from cilantro.constants.overlay_network import *
# from cilantro.storage.vkbook import VKBook
# from cilantro.constants.ports import DHT_PORT
# import time
#
# def run_node(node_type, idx, use_ips=None):
#
#     from vmnet.comm import send_to_file
#     from cilantro.utils.lprocess import LProcess
#     from cilantro.nodes.factory import NodeFactory
#     from cilantro.protocol.overlay.event import Event
#     from cilantro.constants.overlay_network import MIN_BOOTSTRAP_NODES
#     from cilantro.protocol.overlay.daemon import OverlayClient
#     from cilantro.protocol.overlay.kademlia.utils import digest
#     from cilantro.constants.ports import DHT_PORT
#     from cilantro.protocol.comm.socket_auth import SocketAuth
#     import asyncio, os, ujson as json, zmq.asyncio, zmq
#     from cilantro.storage.vkbook import VKBook
#     from threading import Thread
#     VKBook.setup()
#
#     from cilantro.logger import get_logger
#     log = get_logger('{}_{}'.format(node_type.upper(), idx))
#     loop = asyncio.get_event_loop()
#     ctx = zmq.asyncio.Context()
#     creds = VKBook.constitution[node_type][idx]
#     ip = os.getenv('HOST_IP')
#
#     if node_type == 'masternodes':
#         NodeFactory.run_masternode(creds['sk'], ip)
#     elif node_type == 'witnesses':
#         NodeFactory.run_witness(creds['sk'], ip)
#     elif node_type == 'delegates':
#         NodeFactory.run_delegate(creds['sk'], ip)
#
#
# class TestFullNode(BaseTestCase):
#     log = get_logger(__name__)
#     config_file = join(dirname(cilantro.__path__[0]), 'vmnet_configs', 'cilantro-2-2-2-bootstrap.json')
#     environment = {'CONSTITUTION_FILE': '2-2-2.json'}
#     enable_ui = False
#     timeout_delay = 60
#
#     def callback(self, data):
#         self.nodes_complete = self.nodes_complete.union(data)
#         self._success_msg()
#         self.end_test()
#
#     def _success_msg(self):
#         self.log.success('=' * 128)
#         self.log.success('\t{} SUCCEEDED\t\t'.format(self.id()))
#         self.log.success('=' * 128)
#
#     def succeeded(self):
#         return set(self.ns) == self.nodes_complete
#
#     def timeout(self):
#         self.assertTrue(self.succeeded())
#         self._success_msg()
#
#     def setUp(self):
#         super().setUp()
#         self.nodes_complete = set()
#         self.ns = self.groups['masternode'] + self.groups['witness'] + self.groups['delegate']
#
#     def test_full_node_connectivity(self):
#
#         self.execute_python(self.groups['delegate'][0], wrap_func(run_node, 'delegates', 0))
#         self.execute_python(self.groups['delegate'][1], wrap_func(run_node, 'delegates', 1))
#         self.execute_python(self.groups['witness'][0], wrap_func(run_node, 'witnesses', 0))
#         self.execute_python(self.groups['witness'][1], wrap_func(run_node, 'witnesses', 1))
#
#         time.sleep(10)
#         self.execute_python(self.groups['masternode'][0], wrap_func(run_node, 'masternodes', 0))
#         time.sleep(10)
#         self.execute_python(self.groups['masternode'][1], wrap_func(run_node, 'masternodes', 1))
#
#         file_listener(self, self.callback, self.timeout, self.timeout_delay)
#
#     def test_full_node_connectivity_down_and_up(self):
#
#         self.execute_python(self.groups['delegate'][0], wrap_func(run_node, 'delegates', 0))
#         self.execute_python(self.groups['delegate'][1], wrap_func(run_node, 'delegates', 1))
#         self.execute_python(self.groups['witness'][0], wrap_func(run_node, 'witnesses', 0))
#         self.execute_python(self.groups['witness'][1], wrap_func(run_node, 'witnesses', 1))
#
#         time.sleep(10)
#         self.execute_python(self.groups['masternode'][0], wrap_func(run_node, 'masternodes', 0))
#         time.sleep(10)
#         self.restart_node(self.groups['masternode'][0])
#         self.execute_python(self.groups['masternode'][1], wrap_func(run_node, 'masternodes', 1))
#
#         file_listener(self, self.callback, self.timeout, self.timeout_delay)
#
# if __name__ == '__main__':
#     unittest.main()
