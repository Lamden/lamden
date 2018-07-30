import unittest, cilantro, asyncio, socket, time, os, select
from unittest import TestCase
from unittest.mock import patch
from cilantro.protocol.overlay.network import Network
from cilantro.protocol.overlay.node import Node
from cilantro.protocol.overlay.ironhouse import Ironhouse
from cilantro.protocol.overlay.protocol import KademliaProtocol
from cilantro.protocol.overlay.storage import ForgetfulStorage
from cilantro.protocol.overlay.utils import digest
from cilantro.db import VKBook
from os.path import exists, dirname
from threading import Timer
from cilantro.utils.test.overlay import *

def stop(self):
    self.a_net.stop()
    self.b_net.stop()
    self.evil_net.stop()
    self.loop.call_soon_threadsafe(self.loop.stop)

class TestNetwork(TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.a = genkeys('06391888e37a48cef1ded85a375490df4f9b2c74f7723e88c954a055f3d2685a')
        self.b = genkeys('91f7021a9e8c65ca873747ae24de08e0a7acf58159a8aa6548910fe152dab3d8')
        self.evil = genkeys('c5cb6d3ac7d644df8c72b613d57e4c47df6107989e584863b86bde47df704464')
        self.off = genkeys('8ddaf072b9108444e189773e2ddcb4cbd2a76bbf3db448e55d0bfc131409a197')
        self.a_net = Network(sk=self.a['sk'],
                            network_port=3321,
                            keyname='a', wipe_certs=True,
                            loop=self.loop)
        self.b_net = Network(sk=self.b['sk'],
                            network_port=4321,
                            keyname='b', wipe_certs=True,
                            loop=self.loop)
        self.evil_net = Network(sk=self.evil['sk'],
                            network_port=5321,
                            keyname='evil', wipe_certs=True,
                            loop=self.loop)
        self.off_node = Node(
            digest(self.off['vk']), ip='127.0.0.1', port=6321, public_key=self.off['curve_key']
        )

    def test_attributes(self):
        def run(self):
            stop(self)

        self.assertIsInstance(self.a_net.stethoscope_sock, socket.socket)
        self.assertIsInstance(self.a_net.ironhouse, Ironhouse)
        self.assertIsInstance(self.a_net.node, Node)
        self.assertEqual(self.a_net.node.public_key, self.a['curve_key'])
        self.assertEqual(self.b_net.node.public_key, self.b['curve_key'])
        self.assertEqual(self.a_net.node.id, digest(self.a['vk']))
        self.assertEqual(self.b_net.node.id, digest(self.b['vk']))

        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()

    def test_connection(self):
        def run(self):
            self.a_net.connect_to_neighbor(self.b_net.node)
            self.assertTrue(len(self.a_net.connections.keys()) == 1)
            stop(self)

        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()

    def test_authenticate(self):
        def run(self):
            stop(self)

        self.assertTrue(self.loop.run_until_complete(asyncio.ensure_future(
            self.b_net.authenticate(self.a_net.node))))
        self.assertTrue(self.loop.run_until_complete(asyncio.ensure_future(
            self.a_net.authenticate(self.b_net.node))))

        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()

    def test_authenticate_fail(self):
        def run(self):
            stop(self)

        self.assertFalse(self.loop.run_until_complete(asyncio.ensure_future(
            self.a_net.authenticate(self.evil_net.node))))
        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()

    def test_authenticate_timeout(self):
        def run(self):
            stop(self)

        self.assertFalse(self.loop.run_until_complete(asyncio.ensure_future(
            self.a_net.authenticate(self.off_node))))
        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()

    def test_connect_to_neighbor(self):
        def run(self):
            self.a_net.connect_to_neighbor(self.b_net.node)
            time.sleep(0.1) # To allow the server side to accept connecetions
            stop(self)

        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()

    def test_connect_to_neighbor_fail(self):
        def run(self):
            self.evil_net.node.ip = '127.0.0.255'
            self.a_net.connect_to_neighbor(self.evil_net.node)
            self.assertEqual(self.a_net.connections, {})
            stop(self)

        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()

    def test_connect_to_neighbor_disconnect(self):
        def run(self):
            conn = self.a_net.connect_to_neighbor(self.b_net.node)
            time.sleep(0.1)
            conn.shutdown(socket.SHUT_RDWR)
            self.b_net.stop()
            time.sleep(0.1)
            self.assertEqual(self.a_net.connections, {})
            stop(self)

        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()

    def test_listen(self):
        def run(self):
            stop(self)

        self.assertIsInstance(self.a_net.protocol, KademliaProtocol)
        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()

    def test_bootstrap(self):
        def run(self):
            stop(self)
        result = self.loop.run_until_complete(
            asyncio.ensure_future(self.a_net.bootstrap([
                ('127.0.0.1', 3321),
                ('127.0.0.1', 4321)
            ]))
        )
        self.assertEqual([3321,4321], sorted([n.port for n in result]))
        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()

    def test_bootstrap_cached(self):
        def run(self):
            stop(self)
        result = self.loop.run_until_complete(
            asyncio.ensure_future(self.a_net.bootstrap([
                ('127.0.0.1', 3321),
                ('127.0.0.1', 4321)
            ]))
        )
        result = self.loop.run_until_complete(
            asyncio.ensure_future(self.a_net.bootstrap([
                ('127.0.0.1', 3321)
            ]))
        )
        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()

    @patch('cilantro.protocol.overlay.protocol.KademliaProtocol.getRefreshIDs')
    def test_refresh_table(self, getRefreshIDs):
        def run(self):
            stop(self)

        def ids():
            return [
                b"\xaa\xd0\xed\x91O\xa4e'\x06\xdd7\xf8\xf9\xe46p\x9f\x9a\xa1Y",
                b'\x8e\xd4k+\xf6\x10\x9f\xe3\xcf~3@\xca\xee\xc6\x01\r^\xca\x8b'
            ]

        getRefreshIDs.side_effect = ids
        result = self.loop.run_until_complete(
            asyncio.ensure_future(self.a_net.bootstrap([
                ('127.0.0.1', 3321),
                ('127.0.0.1', 4321)
            ]))
        )

        self.a_net.refresh_table()
        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()

    @patch('cilantro.protocol.overlay.network.Network.bootstrappableNeighbors')
    def test_save_load_state(self, bootstrappableNeighbors):
        def run(self):
            stop(self)
        def fn():
            return [('127.0.0.1', 4321, b'^U%HQr(I&^6YihbUAf4HaFQ%*v7gqcy?jwm^KK-{')]

        bootstrappableNeighbors.side_effect = fn

        self.assertTrue(self.a_net.saveState('state.tmp'))
        state = self.a_net.loadState('state.tmp')
        os.remove('state.tmp')
        self.assertEqual(state,{'alpha': 3,
            'id': b"\xaa\xd0\xed\x91O\xa4e'\x06\xdd7\xf8\xf9\xe46p\x9f\x9a\xa1Y",
            'ksize': 20,
            'neighbors': [('127.0.0.1', 4321, b'^U%HQr(I&^6YihbUAf4HaFQ%*v7gqcy?jwm^KK-{')]})

        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()

    def test_save_fail(self):
        def run(self):
            stop(self)
        self.assertFalse(self.a_net.saveState('state.tmp'))
        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()


    def test_lookup_ip(self):
        def run(self):
            stop(self)

        result = self.loop.run_until_complete(
            asyncio.ensure_future(
                self.a_net.lookup_ip(self.a['vk'])
            ))

        self.assertEqual(self.a_net.node, result)

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

        self.assertIsNone(result)

        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()

    def test_lookup_ip_with_neighbors(self):
        def run(self):
            stop(self)
        # Bootstrap first
        self.loop.run_until_complete(
            asyncio.ensure_future(self.a_net.bootstrap([
                ('127.0.0.1', 3321),
                ('127.0.0.1', 4321)
            ]))
        )
        # check for b's VK
        result = self.loop.run_until_complete(
            asyncio.ensure_future(
                self.a_net.lookup_ip(self.b['vk'])
            ))

        self.assertEqual(result.id, self.b_net.node.id)

        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()

    def test_lookup_ip_with_neighbors_fail(self):
        def run(self):
            stop(self)
        # Bootstrap first
        self.loop.run_until_complete(
            asyncio.ensure_future(self.a_net.bootstrap([
                ('127.0.0.1', 3321),
                ('127.0.0.1', 4321)
            ]))
        )
        # check for evil's VK
        result = self.loop.run_until_complete(
            asyncio.ensure_future(
                self.a_net.lookup_ip(self.evil['vk'])
            ))

        self.assertIsNone(result)

        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()

    def test_lookup_ip_with_neighbors_using_cache(self):
        def run(self):
            stop(self)

        # Bootstrap first
        self.loop.run_until_complete(
            asyncio.ensure_future(self.a_net.bootstrap([
                ('127.0.0.1', 3321),
                ('127.0.0.1', 4321)
            ]))
        )
        # check for b's VK
        result = self.loop.run_until_complete(
            asyncio.ensure_future(
                self.a_net.lookup_ip(self.b['vk'])
            ))

        self.assertEqual(result.id, self.b_net.node.id)
        self.assertEqual(self.a_net.lookup_ip_in_cache(self.b['vk']), self.b_net.node.ip)

        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()


    def test_lookup_ip_with_neighbors_using_cache_fail(self):
        def run(self):
            self.assertEqual(self.b_net.vkcache, {})
            stop(self)

        # Bootstrap first
        boot = self.loop.run_until_complete(
            asyncio.ensure_future(self.a_net.bootstrap([
                ('127.0.0.1', 3321),
                ('127.0.0.1', 4321)
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

    def test_bootstrap_fail(self):
        def run(self):
            self.assertEqual(self.b_net.vkcache, {})
            stop(self)

        # Bootstrap first
        boot = self.loop.run_until_complete(
            asyncio.ensure_future(self.a_net.bootstrap([]))
        )
        self.assertEqual(boot, [])

        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()

    def test_bootstrap_node_fail(self):
        def run(self):
            self.assertEqual(self.b_net.vkcache, {})
            stop(self)

        # Bootstrap first
        boot = self.loop.run_until_complete(
            asyncio.ensure_future(self.a_net.bootstrap_node(
                ('127.0.0.1', 6321)
            ))
        )
        self.assertIsNone(boot)

        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()

    def tearDown(self):
        self.loop.close()

if __name__ == '__main__':
    unittest.main()
