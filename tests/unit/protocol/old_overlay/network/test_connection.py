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
            self.evil_net.node.ip = '255.0.0.255'
            self.a_net.connect_to_neighbor(self.evil_net.node)
            self.assertEqual(self.a_net.connections, {})
            stop(self)

        t = Timer(0.01, run, [self])
        t.start()
        self.loop.run_forever()

    def test_connect_to_neighbor_disconnect(self):
        def run(self):
            conn = self.a_net.connect_to_neighbor(self.b_net.node)
            time.sleep(0.5)
            self.b_net.stop()
            time.sleep(0.5)
            if self.a_net.connections != {}:
                for c in self.a_net.connections.values():
                    self.assertTrue(c.fileno(), -1)
            else:
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

if __name__ == '__main__':
    unittest.main()
