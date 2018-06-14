import unittest, asyncio
from unittest import TestCase
from cilantro.protocol.overlay.discovery import Discovery
from os.path import exists, dirname
import socket
from threading import Timer

class TestDiscovery(TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.discovery = Discovery()
        self.discovery.loop = self.loop

    def test_listener(self):
        self.discovery.listen_for_crawlers()
        self.assertIsInstance(self.discovery.udp_sock, socket.socket)
        self.assertIsInstance(self.discovery.udp_sock_server, socket.socket)
        self.discovery.udp_sock_server.close()
        self.discovery.udp_sock.close()

    def test_local(self):
        def get_discovered():
            result = future.result()
            self.assertEqual(list(result.keys()), ['127.0.0.1'])
            self.discovery.server.cancel()
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.discovery.udp_sock_server.close()
            self.discovery.udp_sock.close()

        self.discovery.listen_for_crawlers()

        future = asyncio.ensure_future(self.discovery.discover('test'))

        t = Timer(3.1, get_discovered)
        t.start()
        self.loop.run_forever()

    def test_neighbor(self):
        def get_discovered():
            result = future.result()
            self.assertEqual(list(result.keys()), ['127.0.0.1'])
            self.discovery.server.cancel()
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.discovery.udp_sock_server.close()
            self.discovery.udp_sock.close()

        self.discovery.return_asap = True
        self.discovery.min_bootstrap_nodes = 1
        self.discovery.listen_for_crawlers()

        future = asyncio.ensure_future(self.discovery.discover('neighborhood'))

        t = Timer(3.1, get_discovered)
        t.start()
        self.loop.run_forever()

    def tearDown(self):
        self.loop.close()

if __name__ == '__main__':
    unittest.main()
