import unittest, asyncio, socket, time, os
from unittest import TestCase, mock
from unittest.mock import Mock
from unittest.mock import patch
from cilantro.protocol.overlay.network import Network
from cilantro.protocol.overlay.node import Node
from cilantro.protocol.overlay.ironhouse import Ironhouse
from cilantro.protocol.overlay.protocol import KademliaProtocol
from cilantro.protocol.overlay.utils import digest
from cilantro.constants.testnet import *
from threading import Timer
from cilantro.utils.test.overlay import *

def stop(self):
    self.a_net.stop()
    self.b_net.stop()
    self.evil_net.stop()
    self.loop.call_soon_threadsafe(self.loop.stop)

class TestConnection(TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.a = genkeys(TESTNET_MASTERNODES[0]['sk'])
        self.b = genkeys(TESTNET_WITNESSES[0]['sk'])
        self.evil = genkeys('c5cb6d3ac7d644df8c72b613d57e4c47df6107989e584863b86bde47df704464')
        self.off = genkeys(TESTNET_DELEGATES[0]['sk'])
        self.a_net = Network(sk=self.a['sk'],
                            network_port=13321,
                            keyname='a', wipe_certs=True,
                            loop=self.loop)
        self.b_net = Network(sk=self.b['sk'],
                            network_port=14321,
                            keyname='b', wipe_certs=True,
                            loop=self.loop)
        self.evil_net = Network(sk=self.evil['sk'],
                            network_port=15321,
                            keyname='evil', wipe_certs=True,
                            loop=self.loop)
        self.off_node = Node(
            digest(self.off['vk']), ip='127.0.0.1', port=16321, public_key=self.off['curve_key']
        )

    def tearDown(self):
        self.loop.close()

    def test_lookup_ip(self):
        def run(self):
            stop(self)

        result = self.loop.run_until_complete(
            asyncio.ensure_future(
                self.a_net.lookup_ip(self.a['vk'])
            ))

        print(result[0], self.a_net.node)
        self.assertEqual(self.a_net.node, result[0])

        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()

    def test_lookup_ip_fail(self):
        def run(self):
            stop(self)

        result = self.loop.run_until_complete(
            asyncio.ensure_future(
                self.a_net.lookup_ip(self.b['vk'])
            ))

        self.assertEqual(result, (None, False))

        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()

    def test_lookup_ip_with_neighbors(self):
        def run(self):
            stop(self)
        # Bootstrap first
        self.loop.run_until_complete(
            asyncio.ensure_future(self.a_net.bootstrap([
                ('127.0.0.1', 13321),
                ('127.0.0.1', 14321)
            ]))
        )
        # check for b's VK
        result = self.loop.run_until_complete(
            asyncio.ensure_future(
                self.a_net.lookup_ip(self.b['vk'])
            ))

        self.assertEqual(result[0].id, self.b_net.node.id)

        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()

    def test_lookup_ip_with_neighbors_fail(self):
        def run(self):
            stop(self)
        # Bootstrap first
        self.loop.run_until_complete(
            asyncio.ensure_future(self.a_net.bootstrap([
                ('127.0.0.1', 13321),
                ('127.0.0.1', 14321)
            ]))
        )
        # check for evil's VK
        node, cached = self.loop.run_until_complete(
            asyncio.ensure_future(
                self.a_net.lookup_ip(self.evil['vk'])
            ))

        self.assertEqual((node, cached), (None, False))

        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()

    def test_lookup_ip_with_neighbors_using_cache(self):
        def run(self):
            stop(self)

        # Bootstrap first
        self.loop.run_until_complete(
            asyncio.ensure_future(self.a_net.bootstrap([
                ('127.0.0.1', 13321),
                ('127.0.0.1', 14321)
            ]))
        )
        # check for b's VK
        node, cached = self.loop.run_until_complete(
            asyncio.ensure_future(
                self.a_net.lookup_ip(self.b['vk'])
            ))

        self.assertEqual(node.id, self.b_net.node.id)
        self.assertEqual(self.a_net.lookup_ip_in_cache(self.b_net.node.id).ip, self.b_net.node.ip)

        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()


    def test_lookup_ip_with_neighbors_using_cache_fail(self):
        def run(self):
            self.assertNotEqual(self.b_net.vkcache, {})
            stop(self)

        # Bootstrap first
        boot = self.loop.run_until_complete(
            asyncio.ensure_future(self.a_net.bootstrap([
                ('127.0.0.1', 13321),
                ('127.0.0.1', 14321)
            ]))
        )

        # Populate B cache
        result = self.loop.run_until_complete(
            asyncio.ensure_future(
                self.b_net.lookup_ip(self.a['vk'])
            ))

        self.assertNotEqual(self.b_net.vkcache, {})
        self.a_net.stop()

        t = Timer(0.1, run, [self])
        t.start()
        self.loop.run_forever()

if __name__ == '__main__':
    unittest.main()
