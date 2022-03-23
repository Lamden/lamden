from unittest import TestCase
from lamden.crypto.wallet import Wallet
from lamden.new_network import Network

import asyncio

GET_ALL_PEERS = "get_all_peers"
GET_LATEST_BLOCK = 'get_latest_block'

class Mock_SocketService():
    def __init__(self, running):
        self.running = running

    @property
    def is_running(self):
        return self.running

class Peer():
    def __init__(self, subscriber_running=True, dealer_running=True):
        self.subscriber = Mock_SocketService(running=subscriber_running)
        self.dealer = Mock_SocketService(running=dealer_running)

    @property
    def is_running(self):
        return self.subscriber.is_running and self.dealer.is_running

class TestMultiNode(TestCase):
    def setUp(self):
        self.networks = []

    def tearDown(self):
        for network in self.networks:
            if network.running:
                network.stop()

    def create_network(self, index=0):
        network = Network(
            wallet=Wallet(),
            socket_base='tcp://127.0.0.1',
            socket_ports=self.create_socket_ports(index),
            testing=True,
            debug=True
        )
        network.ip = '127.0.0.1'
        network.add_action(GET_ALL_PEERS, self.get_peer_list)
        network.add_action(GET_LATEST_BLOCK, self.get_latest_block)
        self.networks.append(network)
        network.get_all_peers = self.get_peer_list
        network.router.cred_provider.get_all_peers = self.get_peer_list
        return  network

    def get_peer_list(self):
        return [network.wallet.verifying_key for network in self.networks]

    def get_latest_block(self):
        return {}

    def start_network(self, network):
        tasks = asyncio.gather(
            network.start()
        )
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)
        return res

    def start_all_networks(self):
        for network in self.networks:
            self.start_network(network=network)

    def ensure_async_process(self, process):
        loop = asyncio.get_event_loop()
        asyncio.set_event_loop(loop=loop)
        asyncio.ensure_future(process())

    def await_async_process(self, process):
        tasks = asyncio.gather(
            process()
        )
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)
        return res

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def create_socket_ports(self, index=0):
        return {
            'router': 19000 + index,
            'publisher': 19080 + index,
            'webserver': 18080 + index
        }

    def test_create_instance(self):
        network_1 = self.create_network()

        self.assertIsNotNone(network_1)

    def test_network_starts(self):
        network_1 = self.create_network()

        self.start_network(network=network_1)

        self.assertTrue(network_1.running)

    def test_network_stops(self):
        network_1 = self.create_network()

        self.start_network(network=network_1)

        self.assertTrue(network_1.running)

        network_1.stop()

        self.assertFalse(network_1.running)
        self.assertFalse(network_1.router.running)
        self.assertFalse(network_1.publisher.running)

    def test_connects_to_peer_network(self):
        # Create two network instances
        network_1 = self.create_network()
        self.start_network(network=network_1)
        self.assertTrue(network_1.running)

        network_2 = self.create_network(index=1)
        self.start_network(network=network_2)
        self.assertTrue(network_2.running)

        # connect networks to each other
        network_1.connect(ip=network_2.external_address, vk=network_2.vk)

        # await connections
        self.async_sleep(delay=1)

        # verify connections
        peer_1 = network_1.get_peer(network_2.vk)
        self.assertTrue(peer_1.running)

        peer_2 = network_2.get_peer(network_1.vk)
        self.assertTrue(peer_2.running)

    def test_network_propagates_joined_peers(self):
        # Create two network instances
        network_1 = self.create_network()
        self.start_network(network=network_1)
        self.assertTrue(network_1.running)

        network_2 = self.create_network(index=1)
        self.start_network(network=network_2)
        self.assertTrue(network_2.running)

        # connect networks to each other
        network_1.connect(ip=network_2.external_address, vk=network_2.vk)

        # await connections
        self.async_sleep(delay=1)

        # verify connections
        peer_1 = network_1.get_peer(network_2.vk)
        self.assertTrue(peer_1.running)

        peer_2 = network_2.get_peer(network_1.vk)
        self.assertTrue(peer_2.running)

        # Create new network
        network_3 = self.create_network(index=2)
        self.start_network(network=network_3)

        # Join to one peer on the network
        network_3.connect(ip=network_1.external_address, vk=network_1.vk)

        # await connect
        self.async_sleep(1)

        peer_3 = network_3.get_peer(vk=network_1.vk)
        self.assertTrue(peer_3.running)

        # await connect
        self.async_sleep(1)

        # All networks joined new peer
        for network in self.networks:
            self.assertEqual(2, len(network.peers))
            for peer in network.peers.values():
                self.assertTrue(peer.running)

    def test_num_of_peers_zero(self):
        network_1 = self.create_network()

        self.assertEqual(0, network_1.num_of_peers())

    def test_num_of_peers(self):
        network_1 = self.create_network()

        network_1.peers['node_2'] = {}
        network_1.peers['node_3'] = {}

        self.assertEqual(2, network_1.num_of_peers())

    def test_num_of_peers_connected_zero(self):
        network_1 = self.create_network()

        self.assertEqual(0, network_1.num_of_peers_connected())

    def test_num_of_peers_connected(self):
        network_1 = self.create_network()
        network_1.peers['node_2'] = Peer()
        network_1.peers['node_3'] = Peer(dealer_running=False)

        self.assertEqual(1, network_1.num_of_peers_connected())

    def test_all_peers_connected_True(self):
        network_1 = self.create_network()
        network_1.peers['node_2'] = Peer()
        network_1.peers['node_3'] = Peer()

        self.assertTrue(network_1.all_peers_connected())

    def test_all_peers_connected_False(self):
        network_1 = self.create_network()
        network_1.peers['node_2'] = Peer()
        network_1.peers['node_3'] = Peer(subscriber_running=False)

        self.assertFalse(network_1.all_peers_connected())

    def test_reconnect_peer(self):
        # Create two network instances
        network_1 = self.create_network()
        self.start_network(network=network_1)
        self.assertTrue(network_1.running)

        network_2 = self.create_network(index=1)
        self.start_network(network=network_2)
        self.assertTrue(network_2.running)

        # connect networks to each other
        network_1.connect(ip=network_2.external_address, vk=network_2.vk)

        # await connections
        self.async_sleep(delay=1)

        # Disable Network 2
        network_2.router.pause()

        # Call reconnect loop on other network
        peer = network_1.get_peer(vk=network_2.vk)
        peer.dealer.check_connection()
        self.async_sleep(delay=1)

        self.assertFalse(peer.is_running)
        self.assertTrue(peer.reconnecting)

        # Enable Network 2
        network_2.router.unpause()

        # await Network 1 reconnects to network 2
        self.async_sleep(delay=2.5)

        net_1_all_connected = network_1.all_peers_connected()
        net_2_all_connected = network_2.all_peers_connected()

        self.assertTrue(net_1_all_connected)
        self.assertTrue(net_2_all_connected)




