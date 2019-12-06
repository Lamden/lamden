# from vmnet.testcase import BaseTestCase
# from vmnet.comm import file_listener
# import unittest, time, random, vmnet, cilantro, asyncio, ujson as json, os
# import zmq, zmq.asyncio
# from os.path import join, dirname
# from cilantro_ee.utils.test.mp_test_case import vmnet_test, wrap_func
# from cilantro_ee.core.logger.base import get_logger
#
# def run_node(node_type, idx, addr_idxs):
#     # NOTE: addr_idxs represents what each node has already discovered
#     from vmnet.comm import send_to_file
#     from cilantro_ee.services.overlay.kademlia.network import Network
#     from cilantro_ee.services.overlay.kademlia.utils import digest
#     from cilantro_ee.services.overlay.kademlia.node import Node
#     from cilantro_ee.constants.ports import DHT_PORT
#     from cilantro_ee.constants.overlay_network import MIN_DISCOVERY_NODES
#     from cilantro_ee.utils.keys import Keys
#     import asyncio, os, ujson as json
#     import zmq, zmq.asyncio
#     from os import getenv as env
#     from cilantro_ee.services.storage.vkbook import VKBook
#     VKBook.setup()
#
#     # NOTE: This logic should be improved. There are no utilities for this right now
#     all_ips = env('NODE').split(',')
#     node_objs = []
#     for nt in VKBook.constitution:
#         if nt in ('masternodes', 'delegates'):
#             for creds in VKBook.constitution[nt]:
#                 vk = creds['vk']
#                 node_id = digest(vk)
#                 ip = all_ips[len(node_objs)]
#                 node_objs.append(Node(node_id=node_id, vk=vk, ip=ip, port=DHT_PORT))
#
#     addrs = [node_objs[i] for i in addr_idxs]
#
#     async def check_nodes():
#         await asyncio.sleep(1)
#         await n.bootstrap(addrs)
#         while len(n.routing_table.get_my_neighbors()) < MIN_DISCOVERY_NODES:
#             await asyncio.sleep(2)
#         if len(n.routing_table.get_my_neighbors()) >= MIN_DISCOVERY_NODES:
#             send_to_file(env('HOST_NAME'))
#
#     from cilantro_ee.core.logger import get_logger
#     log = get_logger('{}_{}'.format(node_type, idx))
#     loop = asyncio.new_event_loop()
#     asyncio.set_event_loop(loop)
#     ctx = zmq.asyncio.Context()
#     Keys.setup(VKBook.constitution[node_type][idx]['sk'])
#     log.test('Starting {}_{}'.format(node_type, idx))
#     n = Network(Keys.vk, ctx)
#     n.tasks.clear()
#     n.tasks += [
#         n.process_requests(),
#         check_nodes()
#     ]
#     n.start()
#
# class TestBootstrap(BaseTestCase):
#     log = get_logger(__name__)
#     config_file = join(dirname(cilantro.__path__[0]), 'vmnet_configs', 'cilantro-nodes-4.json')
#     environment = {'CONSTITUTION_FILE': 'vk_dump.json'}
#     enable_ui = False
#
# ################################################################################
# #   Test Setup
# ################################################################################
#
#     def setUp(self):
#         super().setUp()
#         self.all_nodes = set(self.groups['node'])
#         self.nodes_complete = set()
#
#     def tearDown(self):
#         file_listener(self, self.callback, self.timeout, 20)
#         super().tearDown()
#
#     def success(self):
#         self.log.success('=' * 128)
#         self.log.success('\t{} SUCCEEDED\t\t'.format(self.id()))
#         self.log.success('=' * 128)
#
#     def callback(self, data):
#         for node in data:
#             self.nodes_complete.add(node)
#         if self.nodes_complete == self.all_nodes:
#             self.success()
#             self.end_test()
#
#     def timeout(self):
#         self.assertEqual(self.nodes_complete, self.all_nodes)
#
# ################################################################################
# #   Tests
# ################################################################################
#
#     def test_regular_all_masters(self):
#         self.execute_python('node_1', wrap_func(run_node, 'masternodes', 0, [1]))
#         self.execute_python('node_2', wrap_func(run_node, 'masternodes', 1, [0,1]))
#         self.execute_python('node_3', wrap_func(run_node, 'delegates', 0, [0,1,2]))
#         self.execute_python('node_4', wrap_func(run_node, 'delegates', 1, [0,1,2,3]))
#         time.sleep(10)
#
#     def test_regular_one_master(self):
#         self.all_nodes.remove('node_2')
#         self.execute_python('node_1', wrap_func(run_node, 'masternodes', 0, [0]))
#         self.execute_python('node_3', wrap_func(run_node, 'delegates', 0, [0,2]))
#         self.execute_python('node_4', wrap_func(run_node, 'delegates', 1, [0,2,3]))
#
#     def test_late_delegate(self):
#         self.execute_python('node_1', wrap_func(run_node, 'masternodes', 0, [0]))
#         self.execute_python('node_2', wrap_func(run_node, 'masternodes', 1, [0,1]))
#         self.execute_python('node_3', wrap_func(run_node, 'delegates', 0, [0,1,2]))
#         self.log.test('Waiting 10 seconds before spinning up last node')
#         time.sleep(10)
#         self.execute_python('node_4', wrap_func(run_node, 'delegates', 1, [0,1,2,3]))
#
#     def test_one_master_late_delegate(self):
#         self.all_nodes.remove('node_2')
#         self.execute_python('node_1', wrap_func(run_node, 'masternodes', 0, [0]))
#         self.execute_python('node_3', wrap_func(run_node, 'delegates', 0, [0,2]))
#         self.log.test('Waiting 10 seconds before spinning up last node')
#         time.sleep(10)
#         self.execute_python('node_4', wrap_func(run_node, 'delegates', 1, [0,2,3]))
#
#     def test_one_master_down_up(self):
#         self.all_nodes.remove('node_2')
#         self.execute_python('node_1', wrap_func(run_node, 'masternodes', 0, [0]))
#         self.execute_python('node_3', wrap_func(run_node, 'delegates', 0, [0,2]))
#         self.kill_node('node_1')
#         self.execute_python('node_4', wrap_func(run_node, 'delegates', 1, [2,3]))
#         self.log.test('Waiting 10 seconds before spinning up master node again')
#         time.sleep(10)
#         self.start_node('node_1')
#         self.execute_python('node_1', wrap_func(run_node, 'masternodes', 0, [0,2,3]))
#
#     def test_one_late_masternode(self):
#         self.all_nodes.remove('node_2')
#         self.execute_python('node_3', wrap_func(run_node, 'delegates', 0, [2]))
#         self.execute_python('node_4', wrap_func(run_node, 'delegates', 1, [2,3]))
#         self.log.test('Waiting 10 seconds before spinning up master node')
#         time.sleep(10)
#         self.execute_python('node_1', wrap_func(run_node, 'masternodes', 0, [0,2,3]))
#
#     def test_race_conditions(self):
#         self.execute_python('node_1', wrap_func(run_node, 'masternodes', 0, [0]))
#         self.execute_python('node_2', wrap_func(run_node, 'masternodes', 1, [1]))
#         self.execute_python('node_3', wrap_func(run_node, 'delegates', 0, [0,2]))
#         self.execute_python('node_4', wrap_func(run_node, 'delegates', 1, [1,3]))
#
# if __name__ == '__main__':
#     unittest.main()
