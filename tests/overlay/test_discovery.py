import unittest, asyncio
from unittest import TestCase
from cilantro.protocol.overlay.discovery import Discovery
from os.path import exists, dirname
import socket
from threading import Timer

# class TestDiscovery(TestCase):
#     def setUp(self):
#         self.loop = asyncio.new_event_loop()
#         asyncio.set_event_loop(self.loop)
#         self.discovery = Discovery()
#         self.discovery.loop = self.loop
#
#     def test_listener(self):
#         def get_discovered():
#             self.discovery.stop_discovery()
#             self.loop.call_soon_threadsafe(self.loop.stop)
#
#         self.discovery.listen_for_crawlers()
#         self.assertIsInstance(self.discovery.udp_sock, socket.socket)
#         self.assertIsInstance(self.discovery.udp_sock_server, socket.socket)
#
#         t = Timer(0.01, get_discovered)
#         t.start()
#         self.loop.run_forever()
#
#     def test_local(self):
#         self.discovery.max_wait = 0.25
#         self.discovery.listen_for_crawlers()
#
#         fut = asyncio.ensure_future(self.discovery.discover('test'))
#         result = self.loop.run_until_complete(fut)
#         self.assertEqual(list(result.keys()), ['127.0.0.1'])
#         self.discovery.stop_discovery()
#         self.loop.call_soon_threadsafe(self.loop.stop)
#
#
#
#     def test_neighbor(self):
#
#         self.discovery.max_wait = 0.5
#         self.discovery.return_asap = True
#         self.discovery.min_bootstrap_nodes = 1
#         self.discovery.listen_for_crawlers()
#
#         fut = asyncio.ensure_future(self.discovery.discover('neighborhood'))
#         result = self.loop.run_until_complete(fut)
#         self.assertEqual(list(result.keys()), ['127.0.0.1'])
#         self.discovery.stop_discovery()
#         self.loop.call_soon_threadsafe(self.loop.stop)
#
#     def test_stop_discovery(self):
#         def run():
#             self.discovery.stop_discovery()
#             self.assertTrue(self.discovery.server.done())
#             self.loop.call_soon_threadsafe(self.loop.stop)
#
#         self.discovery.listen_for_crawlers()
#
#         t = Timer(0.01, run)
#         t.start()
#         self.loop.run_forever()
#
#     def tearDown(self):
#         self.loop.close()

if __name__ == '__main__':
    unittest.main()
