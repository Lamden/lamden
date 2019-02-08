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
# def run_node(node_type, idx, all_ips=None):
#     from unittest.mock import MagicMock
#     from vmnet.comm import send_to_file
#     from cilantro.utils.lprocess import LProcess
#     from cilantro.protocol.overlay.daemon import OverlayServer, OverlayClient
#     from cilantro.protocol.overlay.handshake import Handshake
#     from cilantro.protocol.executors.manager import ExecutorManager
#     from cilantro.protocol.overlay.auth import Auth
#     import asyncio, os, ujson as json, zmq.asyncio, zmq, time
#     from cilantro.storage.vkbook import VKBook
#     from cilantro.protocol.comm.socket_manager import SocketManager
#     VKBook.setup()
#     PORT = 9432
#     name = os.getenv('HOST_NAME')
#     ip = os.getenv('HOST_IP')
#
#     def _received_sub_msg(m):
#         name = os.getenv('HOST_NAME')
#         log.test('SUB:: node {} got {}'.format(name, m))
#         all_nodes.add(m[1].decode())
#         if len(all_nodes) == 5:
#             send_to_file(name)
#
#     async def _listen_sub(s):
#         socket, url = s
#         log.test('listening to {}'.format(url))
#         while True:
#             msg = await socket.recv_multipart()
#             _received_sub_msg(msg)
#
#     def _received_event(e):
#         name = os.getenv('HOST_NAME')
#         if e.get('status') == 'ready':
#             log.test('node {} got event ready'.format(name))
#
#     async def _send_msgs():
#         await asyncio.sleep(15)
#         msg = [filter, name.encode()]
#         log.test('Sending msgs...'.format(msg))
#         pub_sock.send_multipart(msg)
#
#     from cilantro.logger import get_logger
#     log = get_logger('{}_{}'.format(node_type.upper(), idx))
#     loop = asyncio.get_event_loop()
#     creds = VKBook.constitution[node_type][idx]
#     sk = creds['sk']
#     Auth.setup(sk)
#     ctx, auth = Auth.secure_context(async=True)
#     overlay_proc = LProcess(target=OverlayServer, args=(sk,))
#     overlay_proc.start()
#
#     domain = '*'
#     protocol = 'tcp'
#     filter = b''
#     secure = True
#     all_nodes = set()
#
#     log.test('Waiting for OverlayClient/Manager to be READY.')
#     manager = SocketManager(signing_key=sk, loop=loop, context=ctx)
#     log.test('SYSTEM READY.')
#
#     log.test('Creating pub...')
#     pub = manager.create_socket(zmq.PUB, secure=secure, domain=domain)
#     pub.bind(port=PORT, protocol=protocol, ip=ip)
#     pub_sock = pub.socket
#     log.test('done.')
#
#     log.test('Creating subs...')
#     idx = 0
#     subs = []
#     for node_type in ['masternodes', 'delegates', 'witnesses']:
#         for node in VKBook.constitution[node_type]:
#             if ip != all_ips[idx]:
#                 url = 'tcp://{}:{}'.format(all_ips[idx], PORT)
#                 sock = manager.create_socket(zmq.SUB, secure=secure, domain=domain)
#                 sub = sock.socket
#                 sub.setsockopt(zmq.SUBSCRIBE, filter)
#                 sock.connect(port=PORT, vk=node['vk'])
#                 subs.append([sub, url])
#             idx += 1
#     log.test('Done creating subs!')
#     loop.run_until_complete(asyncio.gather(
#         *[_listen_sub(s) for s in subs],
#         _send_msgs()
#     ))
#
#     loop.run_until_complete(_send_msgs())
#
# class TestPubSub(BaseTestCase):
#     log = get_logger(__name__)
#     config_file = join(dirname(cilantro.__path__[0]), 'vmnet_configs', 'cilantro-nodes-6.json')
#     environment = {'CONSTITUTION_FILE': '2-2-2.json'}
#     enable_ui = True
#     timeout_delay = 120
#
#     def callback(self, data):
#         self.nodes_complete = self.nodes_complete.union(data)
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
#         return set(self.ns) == self.nodes_complete
#
#     def timeout(self):
#         self.assertTrue(self.succeeded())
#         self._success_msg()
#
#     def setUp(self):
#         super().setUp()
#         self.all_nodes = set(self.groups['node'])
#         self.all_ips = self.groups_ips['node']
#         self.ns = self.groups['node']
#         self.nodes_complete = set()
#
#     def test_late_joining_pubsub(self):
#
#         self.execute_python(self.ns[2], wrap_func(run_node, 'delegates', 0, self.all_ips))
#         self.execute_python(self.ns[3], wrap_func(run_node, 'delegates', 1, self.all_ips))
#         self.execute_python(self.ns[4], wrap_func(run_node, 'witnesses', 0, self.all_ips))
#         self.execute_python(self.ns[5], wrap_func(run_node, 'witnesses', 1, self.all_ips))
#
#         time.sleep(10)
#         self.execute_python(self.ns[0], wrap_func(run_node, 'masternodes', 0, self.all_ips))
#         time.sleep(10)
#         self.execute_python(self.ns[1], wrap_func(run_node, 'masternodes', 1, self.all_ips))
#
#         file_listener(self, self.callback, self.timeout, self.timeout_delay)
#
#
# if __name__ == '__main__':
#     unittest.main()
