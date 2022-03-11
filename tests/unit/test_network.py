from unittest import TestCase
from lamden.crypto.wallet import Wallet
from lamden.new_network import Network

import asyncio

GET_ALL_PEERS = "get_all_peers"
GET_LATEST_BLOCK = 'get_latest_block'

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

    def await_async_process(self, process):
        tasks = asyncio.gather(
            process()
        )
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)
        return res

    def create_socket_ports(self, index=0):
        return {
            'router': 19000 + index,
            'publisher': 19080 + index,
            'webserver': 18080 + index
        }

    def test_create_instance(self):
        network_1 = self.create_network()

        self.assertIsNotNone(network_1)

    def test_starts(self):
        network_1 = self.create_network()

        self.start_network(network=network_1)

        self.assertTrue(network_1.running)

    def test_stops(self):
        network_1 = self.create_network()

        self.start_network(network=network_1)

        self.assertTrue(network_1.running)

        network_1.stop()

        self.assertFalse(network_1.running)
        self.assertFalse(network_1.router.running)
        self.assertFalse(network_1.publisher.running)

    def test_connects_to_peer_network(self):
        network_1 = self.create_network()
        self.start_network(network=network_1)
        self.assertTrue(network_1.running)

        network_2 = self.create_network(index=1)
        self.start_network(network=network_2)
        self.assertTrue(network_2.running)

        # add peers to each network
        network_1.connect(ip=network_2.external_address, vk=network_2.vk)
        network_2.connect(ip=network_1.external_address, vk=network_1.vk)

        # verify connections
        peer_1 = network_1.get_peer(network_2.vk)
        self.assertTrue(peer_1.running)

        peer_2 = network_2.get_peer(network_1.vk)
        self.assertTrue(peer_2.running)

    def test_network_propagates_joined_peers(self):
        network_1 = self.create_network()
        self.start_network(network=network_1)
        self.assertTrue(network_1.running)

        network_2 = self.create_network(index=1)
        self.start_network(network=network_2)
        self.assertTrue(network_2.running)

        # add peers to each network
        network_1.connect(ip=network_2.external_address, vk=network_2.vk)
        network_2.connect(ip=network_1.external_address, vk=network_1.vk)

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
        peer_3 = network_3.get_peer(vk=network_1.vk)
        self.assertTrue(peer_3.running)

        # All networks joined new peer
        for network in self.networks:
            self.assertEqual(2, len(network.peers))
            for peer in network.peers:
                self.assertTrue(peer.running)






