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
#     from vmnet.comm import send_to_file
#     from cilantro.protocol.overlay.kademlia.network import Network
#     from cilantro.protocol.overlay.discovery import Discovery
#     from cilantro.constants.overlay_network import MIN_BOOTSTRAP_NODES
#     from cilantro.protocol.overlay.kademlia.utils import digest
#     from cilantro.protocol.overlay.kademlia.node import Node
#     from cilantro.constants.ports import DHT_PORT
#     from cilantro.protocol.comm.socket_auth import SocketAuth
#     import asyncio, os, ujson as json
#     from cilantro.storage.vkbook import VKBook
#     VKBook.setup()
#
#     async def check_nodes():
#         while True:
#             await asyncio.sleep(1)
#             send_to_file(json.dumps({
#                 'node': n.node.ip,
#                 'neighbors': n.bootstrappableNeighbors()
#             }))
#
#     async def bootstrap():
#         ip = os.getenv('HOST_IP')
#         hostname = os.getenv('HOST_NAME')
#         log.debug('{} is running Discovery...'.format(ip))
#         if use_ips:
#             await Discovery.discover_nodes(use_ips)
#         else:
#             await Discovery.discover_nodes(ip)
#         assert len(Discovery.discovered_nodes) >= MIN_BOOTSTRAP_NODES, 'Not enough nodes discovered'
#         addrs = [Node(node_id=digest(vk), vk=vk, ip=ip, port=DHT_PORT) for vk, ip in Discovery.discovered_nodes.items()]
#         log.important('{} is running Bootstrap with: {}'.format(ip, addrs))
#         await n.bootstrap(addrs)
#
#     from cilantro.logger import get_logger
#     log = get_logger('{}_{}'.format(node_type.upper(), idx))
#     loop = asyncio.get_event_loop()
#     creds = VKBook.constitution[node_type][idx]
#     Auth.setup(creds['sk'])
#     Discovery.setup()
#     n = Network(node_id=digest(Auth.vk))
#     n.tasks += [
#         Discovery.listen(),
#         bootstrap(),
#         check_nodes()
#     ]
#     n.start()
#
#
# class TestBootStrapWithDiscovery(BaseTestCase):
#     log = get_logger(__name__)
#     config_file = join(dirname(cilantro.__path__[0]), 'vmnet_configs', 'cilantro-nodes-6.json')
#     environment = {'CONSTITUTION_FILE': '2-2-2.json'}
#     enable_ui = False
#     timeout_delay = 30
#
#     def callback(self, data):
#         for d in data:
#             d = json.loads(d)
#             self.node_topology[d['node']] = d['neighbors']
#         if self.succeeded():
#             self._success_msg()
#             self.end_test()
#
#     def _success_msg(self):
#         self.log.success('=' * 128)
#         self.log.success('\t{} SUCCEEDED\t\t'.format(self.id()))
#         self.log.success('=' * 128)
#
#     def succeeded(self):
#         return len(
#             [True for n in self.node_topology if len(self.node_topology[n]) >= MIN_BOOTSTRAP_NODES + 1]
#         ) == len(self.all_nodes)
#
#     def timeout(self):
#         self.assertTrue(self.succeeded())
#         self._success_msg()
#
#     def setUp(self):
#         super().setUp()
#         self.all_nodes = set(self.groups['node'])
#         self.ns = self.groups['node']
#         self.node_topology = {}
#
#     def test_bootstrap_masternodes_last(self):
#
#         self.execute_python(self.ns[2], wrap_func(run_node, 'delegates', 0))
#         self.execute_python(self.ns[3], wrap_func(run_node, 'delegates', 1))
#         self.execute_python(self.ns[4], wrap_func(run_node, 'witnesses', 0))
#         self.execute_python(self.ns[5], wrap_func(run_node, 'witnesses', 1))
#
#         time.sleep(10)
#         self.execute_python(self.ns[0], wrap_func(run_node, 'masternodes', 0))
#         time.sleep(10)
#         self.execute_python(self.ns[1], wrap_func(run_node, 'masternodes', 1))
#         file_listener(self, self.callback, self.timeout, self.timeout_delay)
#
#     def test_bootstrap_masternodes_first(self):
#         nodes = self.groups_ips['node']
#         self.execute_python(self.ns[0], wrap_func(run_node, 'masternodes', 0, [nodes[0]]))
#         time.sleep(10)
#         self.execute_python(self.ns[1], wrap_func(run_node, 'masternodes', 1))
#         time.sleep(10)
#         self.execute_python(self.ns[2], wrap_func(run_node, 'delegates', 0))
#         self.execute_python(self.ns[3], wrap_func(run_node, 'delegates', 1))
#         self.execute_python(self.ns[4], wrap_func(run_node, 'witnesses', 0))
#         self.execute_python(self.ns[5], wrap_func(run_node, 'witnesses', 1))
#
#         file_listener(self, self.callback, self.timeout, self.timeout_delay)
#
#     def test_bootstrap_masternodes_sandwich(self):
#
#         nodes = self.groups_ips['node']
#         self.execute_python(self.ns[0], wrap_func(run_node, 'masternodes', 0, [nodes[0]]))
#         time.sleep(10)
#         self.execute_python(self.ns[2], wrap_func(run_node, 'delegates', 0))
#         self.execute_python(self.ns[3], wrap_func(run_node, 'delegates', 1))
#         self.execute_python(self.ns[4], wrap_func(run_node, 'witnesses', 0))
#         self.execute_python(self.ns[5], wrap_func(run_node, 'witnesses', 1))
#         time.sleep(10)
#         self.execute_python(self.ns[1], wrap_func(run_node, 'masternodes', 1))
#
#         file_listener(self, self.callback, self.timeout, self.timeout_delay)
#
#     def test_bootstrap_masternodes_race_condition(self):
#         nodes = self.groups_ips['node']
#         self.execute_python(self.ns[0], wrap_func(run_node, 'masternodes', 0, [nodes[0]]))
#         self.execute_python(self.ns[1], wrap_func(run_node, 'masternodes', 1, [nodes[1]]))
#         time.sleep(10)
#         self.execute_python(self.ns[2], wrap_func(run_node, 'delegates', 0))
#         self.execute_python(self.ns[3], wrap_func(run_node, 'delegates', 1))
#         self.execute_python(self.ns[4], wrap_func(run_node, 'witnesses', 0))
#         self.execute_python(self.ns[5], wrap_func(run_node, 'witnesses', 1))
#
#         file_listener(self, self.callback, self.timeout, self.timeout_delay)
#
# if __name__ == '__main__':
#     unittest.main()
