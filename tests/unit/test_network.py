from unittest import TestCase
from lamden.crypto.wallet import Wallet
from lamden.new_network import Network
from lamden.peer import Peer
from lamden.sockets.publisher import Publisher
from lamden.sockets.router import Router

import asyncio
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

GET_ALL_PEERS = "get_all_peers"
GET_LATEST_BLOCK = 'get_latest_block'


class TestNetwork(TestCase):
    def setUp(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.networks = []

    def tearDown(self):
        for network in self.networks:
            if network.running:
                network.stop()

        del self.networks

        loop = asyncio.get_event_loop()
        loop.stop()
        loop.close()

    def create_network(self, index=0):
        network = Network(
            wallet=Wallet(),
            socket_ports=self.create_socket_ports(index),
        )
        network.ip = '127.0.0.1'
        network.add_action(GET_ALL_PEERS, self.get_peer_list)
        network.add_action(GET_LATEST_BLOCK, self.get_latest_block)
        self.networks.append(network)
        network.get_all_peers = self.get_peer_list
        network.router.cred_provider.get_all_peers = self.get_peer_list
        return network

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

    def test_init__creates_network_instance(self):
        network_1 = self.create_network()
        self.assertIsInstance(network_1, Network)

    def test_init__creates_publisher_and_router_instances(self):
        network_1 = self.create_network()

        self.assertIsInstance(network_1.publisher, Publisher)
        self.assertIsInstance(network_1.router, Router)

    def test_PROPERTY_is_running__return_TRUE_if_running_is_TRUE(self):
        network_1 = self.create_network()
        network_1.running = True

        self.assertTrue(network_1.is_running)

    def test_PROPERTY_is_running__returns_FALSE_if_running_is_FALSE(self):
        network_1 = self.create_network()
        network_1.running = False

        self.assertFalse(network_1.is_running)

    def test_PROPERTY_publisher_address__returns_concatenated_protocol_ip_and_port(self):
        network_1 = self.create_network()

        port = 8000
        network_1.socket_ports['publisher'] = 8000

        self.assertEqual(f'tcp://*:{port}', network_1.publisher_address)

    def test_PROPERTY_router_address__returns_concatenated_protocol_ip_and_port(self):
        network_1 = self.create_network()

        port = 8000
        network_1.socket_ports['router'] = 8000

        self.assertEqual(f'tcp://*:{port}', network_1.router_address)

    def test_PROPERTY_external_address__returns_concatenated_protocol_ip_and_port(self):
        network_1 = self.create_network()

        port = 8000
        external_ip = '123.456.789.1'
        network_1.socket_ports['router'] = 8000
        network_1.external_ip = external_ip

        self.assertEqual(f'tcp://{external_ip}:{port}', network_1.external_address)

    def test_PROPERTY_vk__returns_wallet_verifying_key(self):
        network_1 = self.create_network()

        self.assertEqual(network_1.wallet.verifying_key, network_1.vk)

    def test_PROPERTY_peer_list__returns_a_list_of_peer_vks(self):
        network_1 = self.create_network()

        for i in range(3):
            wallet = Wallet()
            peer = Peer(
                local_wallet=network_1.wallet,
                server_vk=wallet.verifying_key,
                ip='1.1.1.1',
                get_network_ip=lambda: network_1.external_address
            )
            network_1.peers[peer.server_vk] = peer


        self.assertEqual(3, len(network_1.peer_list))

        for vk in network_1.peers:
            self.assertIsInstance(vk, str)

    def test_METHOD_start(self):
        network_1 = self.create_network()
        network_1.start()
        self.assertTrue(network_1.running)

    def test_METHOD_starting(self):
        network_1 = self.create_network()

        task = asyncio.ensure_future(network_1.starting())

        network_1.publisher.running = True
        network_1.router.running = True

        self.async_sleep(0.2)

        self.assertTrue(task.done())

    def test_MATHOD_stop__does_not_raise_exception(self):
        network_1 = self.create_network()
        network_1.start()

        try:
            network_1.stop()
        except:
            self.fail("Calling stop should not throw exception.")

        self.assertFalse(network_1.running)

    def test_METHOD_add_peer__adds_peer_to_peer_dict(self):
        network_1 = self.create_network()
        wallet = Wallet()
        peer_vk = wallet.verifying_key
        network_1.add_peer(ip='1.1.1.1', vk=peer_vk)

        self.assertEqual(1, len(network_1.peer_list))
        self.assertIsInstance(network_1.peers[peer_vk], Peer)