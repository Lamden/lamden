import json
from unittest import TestCase
from lamden.crypto.wallet import Wallet
from lamden.new_network import Network, EXCEPTION_PORT_NUM_NOT_INT, ACTION_GET_LATEST_BLOCK, ACTION_PING, ACTION_HELLO, ACTION_GET_BLOCK, ACTION_GET_NETWORK
from lamden.peer import Peer
from lamden.sockets.publisher import Publisher
from lamden.sockets.router import Router

import asyncio
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

GET_ALL_PEERS = "get_all_peers"
GET_LATEST_BLOCK = 'get_latest_block'


class MockConstitution:
    def __init__(self):
        self.constitution = dict({
            'masternodes': {},
            'delegates': {}
        })

        self.constitution['masternodes'][Wallet().verifying_key] = "tcp://127.0.0.1:19001"
        self.constitution['masternodes'][Wallet().verifying_key] = "tcp://127.0.0.1:19002"
        self.constitution['delegates'][Wallet().verifying_key] = "tcp://127.0.0.1:19003"
        self.constitution['delegates'][Wallet().verifying_key] = "tcp://127.0.0.1:19004"

    @property
    def all_nodes(self):
        all_nodes = self.constitution.get('masternodes').copy()
        all_nodes.update(self.constitution.get('delegates'))
        return all_nodes

    def add_node(self, vk: str, ip: str, type: str):
        self.constitution[type][vk] = ip

    def make_constitution(self):
        constitution = dict({
            'masternodes': [vk for vk in self.constitution['masternodes'].keys()],
            'delegates': [vk for vk in self.constitution['delegates'].keys()]
        })
        return constitution


class TestNetwork(TestCase):
    def setUp(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.networks = []
        self.router_msg = None

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

    def mock_send_msg(self, to_vk, msg):
        self.router_msg = (to_vk, msg)

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

    def test_METHOD_start_peer__can_start_a_peer(self):
        network_1 = self.create_network()
        wallet = Wallet()
        peer_vk = wallet.verifying_key
        network_1.add_peer(ip='1.1.1.1', vk=peer_vk)

        network_1.start_peer(vk=peer_vk)

        self.async_sleep(0.5)

        self.assertTrue(network_1.peers[peer_vk].reconnecting)

    def test_METHOD_get_peer__can_return_peer_by_vk(self):
        network_1 = self.create_network()
        wallet = Wallet()
        peer_vk = wallet.verifying_key
        network_1.add_peer(ip='1.1.1.1', vk=peer_vk)

        peer = network_1.get_peer(vk=peer_vk)

        self.assertIsInstance(peer, Peer)
        self.assertEqual(peer_vk, peer.server_vk)

    def test_METHOD_get_peer__returns_None_if_no_matching_vk(self):
        network_1 = self.create_network()
        wallet = Wallet()
        peer_vk = wallet.verifying_key
        network_1.add_peer(ip='1.1.1.1', vk=peer_vk)

        peer = network_1.get_peer(vk='testing')

        self.assertIsNone(peer)

    def test_METHOD_get_peer_by_ip__returns_peer_by_matching_ip(self):
        network_1 = self.create_network()
        wallet = Wallet()
        peer_vk = wallet.verifying_key
        peer_ip = '1.1.1.1'
        network_1.add_peer(ip=peer_ip, vk=peer_vk)

        peer = network_1.get_peer_by_ip(ip=peer_ip)

        self.assertEqual(peer_ip, peer.ip)
        self.assertEqual(peer_vk, peer.server_vk)

    def test_METHOD_get_peer_by_ip__returns_None_if_no_matching_ip(self):
        network_1 = self.create_network()
        wallet = Wallet()
        peer_vk = wallet.verifying_key
        peer_ip = '1.1.1.1'
        network_1.add_peer(ip=peer_ip, vk=peer_vk)

        peer = network_1.get_peer_by_ip(ip='2.2.2.2')

        self.assertIsNone(peer)

    def test_METHOD_set_socket__can_set_a_socket(self):
        network_1 = self.create_network()
        new_port = 1234
        network_1.set_socket_port('router', new_port)

        self.assertEqual(new_port, network_1.socket_ports['router'])

    def test_METHOD_set_socket_ports__raises_AttributeError_when_port_num_not_int(self):
        network_1 = self.create_network()

        with self.assertRaises(AttributeError) as error:
            network_1.set_socket_port('router', '1234')

        self.assertEqual(EXCEPTION_PORT_NUM_NOT_INT, str(error.exception))

    def test_METHOD_num_of_peers(self):
        network_1 = self.create_network()
        wallet = Wallet()
        peer_vk = wallet.verifying_key
        peer_ip = '1.1.1.1'
        network_1.add_peer(ip=peer_ip, vk=peer_vk)

        num_of_peers = network_1.num_of_peers()

        self.assertEqual(1, num_of_peers)

    def test_METHOD_num_of_peers_connected(self):
        network_1 = self.create_network()

        wallet_1 = Wallet()
        peer_vk_1 = wallet_1.verifying_key
        peer_ip_1 = '1.1.1.1'
        network_1.add_peer(ip=peer_ip_1, vk=peer_vk_1)

        wallet_2 = Wallet()
        peer_vk_2 = wallet_2.verifying_key
        peer_ip_2 = '2.2.2.2'
        network_1.add_peer(ip=peer_ip_2, vk=peer_vk_2)

        # Set peer_vk_1 as connected
        peer_1 = network_1.get_peer(vk=peer_vk_1)
        peer_1.connected = True

        num_of_peers_connected = network_1.num_of_peers_connected()

        self.assertEqual(1, num_of_peers_connected)

    def test_METHOD_num_of_peers_connected__returns_zero_if_no_peers_exist(self):
        network_1 = self.create_network()

        num_of_peers_connected = network_1.num_of_peers_connected()
        self.assertEqual(0, num_of_peers_connected)

    def test_METHOD_router_callback__returns_and_does_not_raise_exception_if_message_is_not_json(self):
        network_1 = self.create_network()

        try:
            network_1.router_callback(ident_vk_string="", msg={'Test': True})
        except:
            self.fail('Calling router_callback with a non-string message should exit without exception.')

    def test_METHOD_router_callback__returns_and_does_not_raise_exception_if_msg_has_no_action(self):
        network_1 = self.create_network()

        msg = json.dumps({'testing': 'ping'})

        try:
            network_1.router_callback(ident_vk_string="", msg=msg)
        except:
            self.fail('Calling router_callback with a message without an action should not trigger any exceptions.')

        self.assertIsNone(self.router_msg)

    def test_METHOD_router_callback__ping_action_creates_proper_response(self):
        network_1 = self.create_network()
        network_1.router.send_msg = self.mock_send_msg

        ping_msg = json.dumps({'action': ACTION_PING})

        network_1.router_callback(ident_vk_string="testing_vk", msg=ping_msg)

        self.assertIsNotNone(self.router_msg)
        to_vk, msg = self.router_msg

        self.assertIsInstance(to_vk, str)
        self.assertIsInstance(msg, bytes)

        msg_obj = json.loads(msg)
        self.assertEqual(ACTION_PING, msg_obj.get('response'))


    def test_METHOD_router_callback__hello_action_creates_proper_response(self):
        network_1 = self.create_network()
        network_1.router.send_msg = self.mock_send_msg

        hello_msg = json.dumps({'action': ACTION_HELLO, 'ip': 'tcp://127.0.0.1:19000'})
        wallet = Wallet()
        peer_vk = wallet.verifying_key

        network_1.router_callback(ident_vk_string=peer_vk, msg=hello_msg)

        self.assertIsNotNone(self.router_msg)
        to_vk, msg = self.router_msg

        self.assertIsInstance(to_vk, str)
        self.assertIsInstance(msg, bytes)

        msg_obj = json.loads(msg)
        self.assertEqual(ACTION_HELLO, msg_obj.get("response"))
        self.assertEqual(0, msg_obj.get("latest_block_num"))
        self.assertEqual("0", msg_obj.get("latest_hlc_timestamp"))

    def test_METHOD_router_callback__hello_action_adds_peer_if_one_does_not_exist(self):
        network_1 = self.create_network()
        network_1.router.send_msg = self.mock_send_msg

        hello_msg = json.dumps({'action': ACTION_HELLO, 'ip': 'tcp://127.0.0.1:19000'})
        wallet = Wallet()
        peer_vk = wallet.verifying_key

        network_1.router_callback(ident_vk_string=peer_vk, msg=hello_msg)

        self.assertEqual(1, network_1.num_of_peers())

    def test_METHOD_router_callback__hello_action_does_not_add_peer_if_vk_already_exists(self):
        network_1 = self.create_network()

        wallet = Wallet()
        peer_vk = wallet.verifying_key

        network_1.add_peer(vk=peer_vk, ip='tcp://127.0.0.1:19000')
        self.assertEqual(1, network_1.num_of_peers())

        network_1.router.send_msg = self.mock_send_msg
        hello_msg = json.dumps({'action': ACTION_HELLO, 'ip': 'tcp://127.0.0.1:19000'})

        network_1.router_callback(ident_vk_string=peer_vk, msg=hello_msg)

        self.assertEqual(1, network_1.num_of_peers())

    def test_METHOD_router_callback__latest_block_info_action_creates_proper_response(self):
        network_1 = self.create_network()
        network_1.router.send_msg = self.mock_send_msg

        latest_block_info_msg = json.dumps({'action': ACTION_GET_LATEST_BLOCK})
        wallet = Wallet()
        peer_vk = wallet.verifying_key

        network_1.router_callback(ident_vk_string=peer_vk, msg=latest_block_info_msg)

        self.assertIsNotNone(self.router_msg)
        to_vk, msg = self.router_msg

        self.assertIsInstance(to_vk, str)
        self.assertIsInstance(msg, bytes)

        msg_obj = json.loads(msg)
        self.assertEqual(ACTION_GET_LATEST_BLOCK, msg_obj.get("response"))
        self.assertEqual(0, msg_obj.get("number"))
        self.assertEqual("0", msg_obj.get("hlc_timestamp"))

    def test_METHOD_router_callback__get_block_action_creates_proper_response_if_block_exists(self):
        def return_block(v):
            return {
                'number': 1,
                'hlc_timestamp': '1'
            }
        network_1 = self.create_network()
        network_1.router.send_msg = self.mock_send_msg
        network_1.actions[ACTION_GET_BLOCK] = return_block

        latest_block_info_msg = json.dumps({'action': ACTION_GET_BLOCK, 'block_num': 1})
        wallet = Wallet()
        peer_vk = wallet.verifying_key

        network_1.router_callback(ident_vk_string=peer_vk, msg=latest_block_info_msg)

        self.assertIsNotNone(self.router_msg)
        to_vk, msg = self.router_msg

        self.assertIsInstance(to_vk, str)
        self.assertIsInstance(msg, bytes)

        msg_obj = json.loads(msg)
        self.assertEqual(ACTION_GET_BLOCK, msg_obj.get("response"))
        block_info = msg_obj.get("block_info")
        self.assertEqual(1, block_info.get("number"))
        self.assertEqual("1", block_info.get("hlc_timestamp"))


    def test_METHOD_router_callback__get_block_action_creates_proper_response_if_block_does_not_exist(self):
        def return_block(v):
            return None
        network_1 = self.create_network()
        network_1.router.send_msg = self.mock_send_msg
        network_1.actions[ACTION_GET_BLOCK] = return_block

        latest_block_info_msg = json.dumps({'action': ACTION_GET_BLOCK, 'block_num': 1})
        wallet = Wallet()
        peer_vk = wallet.verifying_key

        network_1.router_callback(ident_vk_string=peer_vk, msg=latest_block_info_msg)

        self.assertIsNotNone(self.router_msg)
        to_vk, msg = self.router_msg

        self.assertIsInstance(to_vk, str)
        self.assertIsInstance(msg, bytes)

        msg_obj = json.loads(msg)
        self.assertEqual(ACTION_GET_BLOCK, msg_obj.get("response"))
        block_info = msg_obj.get("block_info")
        self.assertEqual(None, block_info)

    def test_METHOD_router_callback__get_network_action_creates_proper_response(self):

        network_1 = self.create_network()

        constitution = MockConstitution()
        for vk, ip in constitution.all_nodes.items():
            network_1.add_peer(vk=vk, ip=ip)

        constitution.add_node(vk=network_1.vk, ip=network_1.external_address, type="masternodes")

        network_1.router.send_msg = self.mock_send_msg
        network_1.make_constitution = constitution.make_constitution

        latest_block_info_msg = json.dumps({'action': ACTION_GET_NETWORK})
        wallet = Wallet()
        peer_vk = wallet.verifying_key

        network_1.router_callback(ident_vk_string=peer_vk, msg=latest_block_info_msg)

        self.assertIsNotNone(self.router_msg)
        to_vk, msg = self.router_msg

        self.assertIsInstance(to_vk, str)
        self.assertIsInstance(msg, bytes)

        msg_obj = json.loads(msg)
        self.assertEqual(ACTION_GET_NETWORK, msg_obj.get("response"))
        node_list = msg_obj.get("node_list")

        for vk, ip in constitution.all_nodes.items():
            found = False
            for node in node_list:
                if node.get('vk') == vk and node.get('ip') == ip:
                    found = True
                    break

            self.assertTrue(found)

    def test_METHOD_remove_peer(self):
        network_1 = self.create_network()
        peer_vk = Wallet().verifying_key
        network_1.add_peer(vk=peer_vk, ip='tcp://127.0.0.1:19001')

        self.assertEqual(1, network_1.num_of_peers())
        network_1.remove_peer(peer_vk=peer_vk)
        self.assertEqual(0, network_1.num_of_peers())

    def test_METHOD_remove_peer(self):
        network_1 = self.create_network()
        peer_vk = Wallet().verifying_key

        self.assertEqual(0, network_1.num_of_peers())
        try:
            network_1.remove_peer(peer_vk=peer_vk)
        except:
            self.fail("Calling remove_peer when peer doesn't exists should cause no exceptions.")

    def test_METHOD_connected_to_all_peers__task_completes_when_all_peers_are_connected(self):
        network_1 = self.create_network()

        peer_vk_1 = Wallet().verifying_key
        peer_vk_2 = Wallet().verifying_key

        network_1.add_peer(vk=peer_vk_1, ip='tcp://127.0.0.1:19001')
        network_1.add_peer(vk=peer_vk_2, ip='tcp://127.0.0.1:19002')

        task = asyncio.ensure_future(network_1.connected_to_all_peers())

        self.async_sleep(2)
        self.assertFalse(task.done())

        for peer in network_1.peers.values():
            peer.connected = True

        self.async_sleep(2)

        self.assertTrue(task.done())




