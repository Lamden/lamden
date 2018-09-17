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

class TestNetwork(TestCase):
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


    def test_bootstrap(self):
        def run(self):
            stop(self)
        result = self.loop.run_until_complete(
            asyncio.ensure_future(self.a_net.bootstrap([
                ('127.0.0.1', 13321),
                ('127.0.0.1', 14321)
            ]))
        )
        self.assertEqual([13321,14321], sorted([n.port for n in result]))
        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()

    def test_bootstrap_cached(self):
        def run(self):
            stop(self)
        self.loop.run_until_complete(
            asyncio.ensure_future(self.a_net.bootstrap([
                ('127.0.0.1', 13321),
                ('127.0.0.1', 14321)
            ]))
        )
        result = self.loop.run_until_complete(
            asyncio.ensure_future(self.a_net.bootstrap([
                ('127.0.0.1', 13321)
            ]))
        )
        self.assertEqual([13321,14321], sorted([n.port for n in result]))
        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()

    @patch('cilantro.protocol.overlay.protocol.KademliaProtocol.getRefreshIDs')
    def test_refresh_table(self, getRefreshIDs):
        def run(self):
            stop(self)

        def ids():
            return [
                b"\xdb\xea\xea\xfb\xd2\x87S\xac\xfe\x88\xfc\x94\xddQ\xd4p\xec\x0e7v",
                b'\x8e\xd4k+\xf6\x10\x9f\xe3\xcf~3@\xca\xee\xc6\x01\r^\xca\x8b'
            ]

        getRefreshIDs.side_effect = ids
        result = self.loop.run_until_complete(
            asyncio.ensure_future(self.a_net.bootstrap([
                ('127.0.0.1', 13321),
                ('127.0.0.1', 14321)
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
            return [('127.0.0.1', 14321, b'^U%HQr(I&^6YihbUAf4HaFQ%*v7gqcy?jwm^KK-{')]

        bootstrappableNeighbors.side_effect = fn

        self.assertTrue(self.a_net.saveState('state.tmp'))
        state = self.a_net.loadState('state.tmp')
        os.remove('state.tmp')
        self.assertEqual(state,{'ALPHA': 3,
            'id': b"\xdb\xea\xea\xfb\xd2\x87S\xac\xfe\x88\xfc\x94\xddQ\xd4p\xec\x0e7v",
            'KSIZE': 20,
            'neighbors': [('127.0.0.1', 14321, b'^U%HQr(I&^6YihbUAf4HaFQ%*v7gqcy?jwm^KK-{')]})

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
                ('127.0.0.1', 16321)
            ))
        )
        self.assertIsNone(boot)

        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()

if __name__ == '__main__':
    unittest.main()
