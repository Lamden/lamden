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
# def run_node(node_type, idx, addrs):
#     from vmnet.comm import send_to_file
#     from cilantro.protocol.overlay.kademlia.network import Network
#     from cilantro.protocol.overlay.kademlia.utils import digest
#     from cilantro.protocol.overlay.kademlia.node import Node
#     from cilantro.protocol.overlay.auth import Auth
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
#     from cilantro.logger import get_logger
#     log = get_logger('{}_{}'.format(node_type.upper(), idx))
#     loop = asyncio.get_event_loop()
#     creds = VKBook.constitution[node_type][idx]
#     Auth.setup(creds['sk'])
#     n = Network(node_id=digest(Auth.vk))
#     n.tasks += [
#         n.bootstrap(addrs),
#         check_nodes()
#     ]
#     n.start()
#
#
# class TestBootStrap(BaseTestCase):
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
#         self.nodes_complete = set()
#         self.ns = []
#         self.node_topology = {}
#
#         for g, node_type in enumerate(['masternodes', 'delegates', 'witnesses']):
#             for i in range(2):
#                 creds = VKBook.constitution[node_type][i]
#                 vk = creds['vk']
#                 ip = self.groups_ips['node'][i + g * 2]
#                 node_id = digest(vk)
#                 self.ns.append(Node(node_id=node_id, vk=vk, ip=ip, port=DHT_PORT))
#
#     def test_bootstrap_everyone_bootstrap_using_masternodes(self):
#         gs = [
#             [self.ns[0]] + self.ns[2:5],
#             self.ns,
#             [self.ns[2]],
#             self.ns[2:3],
#             self.ns[2:4],
#             self.ns[2:5],
#         ]
#
#         self.execute_python(self.groups['node'][2], wrap_func(run_node, 'delegates', 0, gs[2]))
#         self.execute_python(self.groups['node'][3], wrap_func(run_node, 'delegates', 1, gs[3]))
#         self.execute_python(self.groups['node'][4], wrap_func(run_node, 'witnesses', 0, gs[4]))
#         self.execute_python(self.groups['node'][5], wrap_func(run_node, 'witnesses', 1, gs[5]))
#
#         time.sleep(10)
#         self.execute_python(self.groups['node'][0], wrap_func(run_node, 'masternodes', 0, gs[0]))
#         self.execute_python(self.groups['node'][1], wrap_func(run_node, 'masternodes', 1, gs[1]))
#         file_listener(self, self.callback, self.timeout, self.timeout_delay)
#
#     # NOTE: Supposedly impossible because all nodes are hard-coded
#     # def test_bootstrap_everyone_bootstrap_without_directly_bootstraping_any_masternodes(self):
#     #     gs = [
#     #         [self.ns[2]],
#     #         [self.ns[3]],
#     #         [self.ns[5]],
#     #         [self.ns[4]],
#     #         [self.ns[3]],
#     #         [self.ns[2]]
#     #     ]
#     #
#     #     self.execute_python(self.groups['node'][2], wrap_func(run_node, 'delegates', 0, gs[2]))
#     #     self.execute_python(self.groups['node'][3], wrap_func(run_node, 'delegates', 1, gs[3]))
#     #     self.execute_python(self.groups['node'][4], wrap_func(run_node, 'witnesses', 0, gs[4]))
#     #     self.execute_python(self.groups['node'][5], wrap_func(run_node, 'witnesses', 1, gs[5]))
#     #
#     #     time.sleep(10)
#     #     self.execute_python(self.groups['node'][0], wrap_func(run_node, 'masternodes', 0, gs[0]))
#     #     self.execute_python(self.groups['node'][1], wrap_func(run_node, 'masternodes', 1, gs[1]))
#     #     file_listener(self, self.callback, self.timeout, self.timeout_delay)
#
#     # NOTE: Supposedly impossible because all nodes are hard-coded
#     # def test_bootstrap_everyone_bootstrap_with_one_masternode_isolated(self):
#     #     def timeout_fail():
#     #         for i, ip in enumerate(self.groups_ips['node']):
#     #             if i == 1:
#     #                 self.assertEqual(len(self.node_topology[ip]), 1)
#     #             else:
#     #                 self.assertTrue(len(self.node_topology[ip]) >= 2)
#     #         self._success_msg()
#     #     gs = [
#     #         [self.ns[3]],
#     #         [self.ns[1]], # This masternode only finds itself
#     #         [self.ns[0]],
#     #         [self.ns[4]],
#     #         [self.ns[5]],
#     #         [self.ns[3]]
#     #     ]
#     #
#     #     self.execute_python(self.groups['node'][2], wrap_func(run_node, 'delegates', 0, gs[2]))
#     #     self.execute_python(self.groups['node'][3], wrap_func(run_node, 'delegates', 1, gs[3]))
#     #     self.execute_python(self.groups['node'][4], wrap_func(run_node, 'witnesses', 0, gs[4]))
#     #     self.execute_python(self.groups['node'][5], wrap_func(run_node, 'witnesses', 1, gs[5]))
#     #
#     #     time.sleep(10)
#     #     self.execute_python(self.groups['node'][0], wrap_func(run_node, 'masternodes', 0, gs[0]))
#     #     self.execute_python(self.groups['node'][1], wrap_func(run_node, 'masternodes', 1, gs[1]))
#     #     file_listener(self, self.callback, timeout_fail, self.timeout_delay)
#
# if __name__ == '__main__':
#     unittest.main()
