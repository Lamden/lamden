import json
from unittest import TestCase
from lamden.crypto.wallet import Wallet
from lamden.network import Network, EXCEPTION_PORT_NUM_NOT_INT, ACTION_GET_LATEST_BLOCK, ACTION_PING, ACTION_HELLO, ACTION_GET_BLOCK, ACTION_GET_NETWORK_MAP
from lamden.peer import Peer, LATEST_BLOCK_INFO
from lamden.sockets.publisher import Publisher
from lamden.sockets.router import Router
from lamden.storage import BlockStorage

from contracting.db.driver import ContractDriver, InMemDriver

import asyncio
import uvloop
from pathlib import Path
import shutil

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

GET_ALL_PEERS = "get_all_peers"

class MockNetworkMap:
    def __init__(self, network_map: dict = None):
        self.network_map = dict({
            'masternodes': {},
            'delegates': {}
        })

        if network_map is None:
            self.network_map['masternodes'][Wallet().verifying_key] = "tcp://127.0.0.1:19001"
            self.network_map['masternodes'][Wallet().verifying_key] = "tcp://127.0.0.1:19002"
            self.network_map['delegates'][Wallet().verifying_key] = "tcp://127.0.0.1:19003"
            self.network_map['delegates'][Wallet().verifying_key] = "tcp://127.0.0.1:19004"
        else:
            self.network_map = network_map

    @property
    def all_nodes(self):
        all_nodes = self.network_map.get('masternodes').copy()
        all_nodes.update(self.network_map.get('delegates'))
        return all_nodes

    def add_node(self, vk: str, ip: str, type: str):
        self.network_map[type][vk] = ip

    def make_constitution(self):
        network_map = dict({
            'masternodes': [vk for vk in self.network_map['masternodes'].keys()],
            'delegates': [vk for vk in self.network_map['delegates'].keys()]
        })
        return network_map


class TestNetwork(TestCase):
    def setUp(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.networks = []
        self.router_msg = None
        self.publish_info = None
        self.connect_info = None

        self.called_ip_update = False
        self.called_test_connection = False

        self.driver = ContractDriver(driver=InMemDriver())

        current_path = Path.cwd()
        lamden_storage_directory = f'{current_path}/.lamden'

        try:
            shutil.rmtree(lamden_storage_directory)
        except:
            pass

        self.storage = BlockStorage(home=Path(lamden_storage_directory))

    def tearDown(self):
        for network in self.networks:
            task = asyncio.ensure_future(network.stop())

            while not task.done():
                self.async_sleep(1)

        del self.networks

        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.stop()
        if not loop.is_closed():
            loop.close()

    def create_network(self, index=0):
        network = Network(
            wallet=Wallet(),
            socket_ports=self.create_socket_ports(index),
            local=True,
            driver=self.driver,
            block_storage=self.storage
        )

        self.networks.append(network)

        return network

    def get_peer_list(self):
        return [network.wallet.verifying_key for network in self.networks]

    def add_vk_to_smartcontract(self, node_type, network, vk):
        if node_type == 'masternode':
            current_vks = network.get_masternode_vk_list()
        else:
            current_vks = network.get_delegate_vk_list()

        current_vks.append(vk)

        network.driver.driver.set(
            key=f"{node_type}s.S:members",
            value=current_vks
        )

    def mock_send_msg(self, to_vk, msg_str):
        self.router_msg = (to_vk, msg_str)

    def mock_peer_update_ip(self, new_ip):
        self.called_ip_update = new_ip

    async def mock_peer_test_connection(self):
        self.called_test_connection = True

    def mock_announce_new_peer_connection(self, ip, vk):
        self.publish_info = (ip, vk)

    def mock_connect_peer(self, ip, vk):
        self.connect_info = (ip, vk)

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

    def test_init__new_instance_uses_default_socket_ports(self):
        network_1 =  Network(
            wallet=Wallet()
        )
        self.assertIsInstance(network_1, Network)
        self.assertEqual(19000, network_1.socket_ports.get('router'))
        self.assertEqual(19080, network_1.socket_ports.get('publisher'))
        self.assertEqual(18080, network_1.socket_ports.get('webserver'))

    def test_init__new_instance_create_new_event_loop_if_needed(self):
        loop = asyncio.get_event_loop()
        loop.stop()
        loop.close()
        loop.is_closed()

        network_1 = self.create_network()

        self.assertIsNotNone(network_1.loop)

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

    def test_PROPERTY_publisher_address__returns_concatenated_protocol_ip_and_port_local_if_local_True(self):
        network_1 = self.create_network()

        port = 8000
        network_1.socket_ports['publisher'] = 8000

        self.assertEqual(f'tcp://127.0.0.1:{port}', network_1.publisher_address)

    def test_PROPERTY_publisher_address__returns_concatenated_protocol_ip_and_port_wildcard_if_local_False(self):
        network_1 = self.create_network()
        network_1.local = False

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
        loop = asyncio.get_event_loop()
        loop.run_until_complete(network_1.starting())

        self.assertTrue(network_1.running)

    def test_METHOD_starting(self):
        network_1 = self.create_network()

        task = asyncio.ensure_future(network_1.starting())

        network_1.publisher.running = True
        network_1.router.running = True

        self.async_sleep(0.2)

        self.assertTrue(task.done())

    def test_METHOD_stop__does_not_raise_exception(self):
        network_1 = self.create_network()
        network_1.start()

        try:
            task = asyncio.ensure_future(network_1.stop())

            while not task.done():
                self.async_sleep(1)
        except:
            self.fail("Calling stop should not throw exception.")

        self.assertFalse(network_1.running)

    def test_METHOD_stop__stops_all_peers(self):
        network_1 = self.create_network()
        network_1.start()

        peer_wallet = Wallet()
        peer_vk = peer_wallet.verifying_key

        network_1.create_peer(
            ip='tcp://127.0.0.1:19001',
            vk=peer_vk
        )

        peer = network_1.get_peer(vk=peer_vk)

        peer.start()
        while not peer.is_verifying:
            self.async_sleep(0.1)

        task = asyncio.ensure_future(network_1.stop())

        while not task.done():
            self.async_sleep(0.1)

        peer = network_1.get_peer(vk=peer_vk)
        self.assertFalse(peer.is_running)

    def test_METHOD_create_peer__adds_peer_to_peer_dict(self):
        network_1 = self.create_network()
        wallet = Wallet()
        peer_vk = wallet.verifying_key

        network_1.create_peer(ip='1.1.1.1', vk=peer_vk)

        self.assertEqual(1, len(network_1.peer_list))
        self.assertIsInstance(network_1.peers[peer_vk], Peer)

    def test_METHOD_start_peer__can_start_a_peer(self):
        network_1 = self.create_network()
        wallet = Wallet()
        peer_vk = wallet.verifying_key

        network_1.create_peer(ip='1.1.1.1', vk=peer_vk)

        network_1.start_peer(vk=peer_vk)

        self.async_sleep(0.5)

        self.assertTrue(network_1.peers[peer_vk].reconnecting)

    def test_METHOD_get_peer__can_return_peer_by_vk(self):
        network_1 = self.create_network()
        wallet = Wallet()
        peer_vk = wallet.verifying_key

        network_1.create_peer(ip='1.1.1.1', vk=peer_vk)

        peer = network_1.get_peer(vk=peer_vk)

        self.assertIsInstance(peer, Peer)
        self.assertEqual(peer_vk, peer.server_vk)

    def test_METHOD_get_peer__returns_None_if_no_matching_vk(self):
        network_1 = self.create_network()
        wallet = Wallet()
        peer_vk = wallet.verifying_key

        network_1.create_peer(ip='1.1.1.1', vk=peer_vk)

        peer = network_1.get_peer(vk='testing')

        self.assertIsNone(peer)

    def test_METHOD_get_peer_by_ip__returns_peer_by_matching_ip(self):
        network_1 = self.create_network()
        wallet = Wallet()
        peer_vk = wallet.verifying_key
        peer_ip = '1.1.1.1'

        network_1.create_peer(ip=peer_ip, vk=peer_vk)

        peer = network_1.get_peer_by_ip(ip=peer_ip)

        self.assertEqual(peer_ip, peer.ip)
        self.assertEqual(peer_vk, peer.server_vk)

    def test_METHOD_get_peer_by_ip__returns_None_if_no_matching_ip(self):
        network_1 = self.create_network()
        wallet = Wallet()
        peer_vk = wallet.verifying_key
        peer_ip = '1.1.1.1'

        network_1.create_peer(ip=peer_ip, vk=peer_vk)

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
        network_1.create_peer(ip=peer_ip, vk=peer_vk)

        num_of_peers = network_1.num_of_peers()

        self.assertEqual(1, num_of_peers)

    def test_METHOD_num_of_peers_connected(self):
        network_1 = self.create_network()

        wallet_1 = Wallet()
        peer_vk_1 = wallet_1.verifying_key
        peer_ip_1 = '1.1.1.1'

        network_1.create_peer(ip=peer_ip_1, vk=peer_vk_1)

        wallet_2 = Wallet()
        peer_vk_2 = wallet_2.verifying_key
        peer_ip_2 = '2.2.2.2'

        network_1.create_peer(ip=peer_ip_2, vk=peer_vk_2)

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
        to_vk, msg_str = self.router_msg

        self.assertIsInstance(to_vk, str)
        self.assertIsInstance(msg_str, str)

        msg_obj = json.loads(msg_str)
        self.assertEqual(ACTION_PING, msg_obj.get('response'))


    def test_METHOD_router_callback__hello_action_creates_proper_response(self):
        network_1 = self.create_network()
        network_1.router.send_msg = self.mock_send_msg
        network_1.connect_peer = self.mock_connect_peer

        challenge = 'testing'
        hello_msg = json.dumps({'action': ACTION_HELLO, 'ip': 'tcp://127.0.0.1:19000', 'challenge': challenge})
        wallet = Wallet()
        peer_vk = wallet.verifying_key

        network_1.router_callback(ident_vk_string=peer_vk, msg=hello_msg)

        self.assertIsNotNone(self.router_msg)
        to_vk, msg_str = self.router_msg

        self.assertIsInstance(to_vk, str)
        self.assertIsInstance(msg_str, str)

        msg_obj = json.loads(msg_str)
        self.assertEqual(ACTION_HELLO, msg_obj.get("response"))
        self.assertEqual(0, msg_obj.get("latest_block_number"))
        self.assertEqual("0", msg_obj.get("latest_hlc_timestamp"))
        self.assertEqual(network_1.wallet.sign(challenge), msg_obj.get("challenge_response"))

        # Tried to add peer
        self.assertIsNotNone(self.connect_info)

    def test_METHOD_router_callback__hello_action_adds_peer_if_one_does_not_exist(self):
        network_1 = self.create_network()
        network_1.router.send_msg = self.mock_send_msg

        hello_msg = json.dumps({'action': ACTION_HELLO, 'ip': 'tcp://127.0.0.1:19000', 'challenge': 'testing'})
        wallet = Wallet()
        peer_vk = wallet.verifying_key
        self.add_vk_to_smartcontract(node_type='masternode', network=network_1, vk=peer_vk)

        network_1.router_callback(ident_vk_string=peer_vk, msg=hello_msg)

        self.assertEqual(1, network_1.num_of_peers())

    def test_METHOD_router_callback__hello_action_does_not_add_peer_if_vk_already_exists(self):
        network_1 = self.create_network()

        wallet = Wallet()
        peer_vk = wallet.verifying_key

        network_1.create_peer(vk=peer_vk, ip='tcp://127.0.0.1:19000')
        self.assertEqual(1, network_1.num_of_peers())

        network_1.router.send_msg = self.mock_send_msg
        hello_msg = json.dumps({'action': ACTION_HELLO, 'ip': 'tcp://127.0.0.1:19000', 'challenge': 'testing'})

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
        self.assertIsInstance(msg, str)

        msg_obj = json.loads(msg)
        self.assertEqual(ACTION_GET_LATEST_BLOCK, msg_obj.get("response"))
        self.assertEqual(0, msg_obj.get("number"))
        self.assertEqual("0", msg_obj.get("hlc_timestamp"))

    def test_METHOD_router_callback__get_block_action_creates_proper_response_if_block_exists(self):
        network_1 = self.create_network()
        network_1.router.send_msg = self.mock_send_msg

        latest_block_info_msg = json.dumps({'action': ACTION_GET_BLOCK, 'block_num': 1})
        wallet = Wallet()
        peer_vk = wallet.verifying_key

        network_1.block_storage.store_block(block={
            'number': 1,
            'hash': "1a2b3c",
            'hlc_timestamp': '1',
            'processed': {
                'hash': 'testing'
            }
        })

        network_1.router_callback(ident_vk_string=peer_vk, msg=latest_block_info_msg)

        self.assertIsNotNone(self.router_msg)
        to_vk, msg = self.router_msg


        self.assertIsInstance(to_vk, str)
        self.assertIsInstance(msg, str)

        msg_obj = json.loads(msg)


        self.assertEqual(ACTION_GET_BLOCK, msg_obj.get("response"))
        block_info = msg_obj.get("block_info")

        self.assertIsNotNone(msg_obj)
        self.assertEqual(1, block_info.get("number"))
        self.assertEqual("1a2b3c", block_info.get("hash"))
        self.assertEqual("1", block_info.get("hlc_timestamp"))

    def test_METHOD_router_callback__get_block_action_creates_proper_response_if_block_does_not_exist(self):
        network_1 = self.create_network()
        network_1.router.send_msg = self.mock_send_msg

        latest_block_info_msg = json.dumps({'action': ACTION_GET_BLOCK, 'block_num': 1})
        wallet = Wallet()
        peer_vk = wallet.verifying_key

        network_1.router_callback(ident_vk_string=peer_vk, msg=latest_block_info_msg)

        self.assertIsNotNone(self.router_msg)
        to_vk, msg = self.router_msg

        self.assertIsInstance(to_vk, str)
        self.assertIsInstance(msg, str)

        msg_obj = json.loads(msg)
        self.assertEqual(ACTION_GET_BLOCK, msg_obj.get("response"))
        block_info = msg_obj.get("block_info")
        self.assertEqual(None, block_info)

    def test_METHOD_router_callback__get_network_action_creates_proper_response(self):
        network_1 = self.create_network()

        mock_network_map = MockNetworkMap()

        for vk, ip in mock_network_map.all_nodes.items():
            self.add_vk_to_smartcontract(node_type='masternode', network=network_1, vk=vk)
            network_1.create_peer(vk=vk, ip=ip)

        network_1.router.send_msg = self.mock_send_msg

        latest_block_info_msg = json.dumps({'action': ACTION_GET_NETWORK_MAP})
        wallet = Wallet()
        peer_vk = wallet.verifying_key

        network_1.router_callback(ident_vk_string=peer_vk, msg=latest_block_info_msg)

        self.assertIsNotNone(self.router_msg)
        to_vk, msg = self.router_msg

        self.assertIsInstance(to_vk, str)
        self.assertIsInstance(msg, str)

        msg_obj = json.loads(msg)
        self.assertEqual(ACTION_GET_NETWORK_MAP, msg_obj.get("response"))
        network_map = msg_obj.get("network_map")

        return_network_map = MockNetworkMap(network_map=network_map)

        self.assertTrue(len(mock_network_map.all_nodes), len(return_network_map.all_nodes))

        for vk, ip in mock_network_map.all_nodes.items():
            self.assertEqual(ip, mock_network_map.all_nodes[vk])

    def test_METHOD_make_network_map(self):
        network_1 = self.create_network()

        node_list = [
            {
                'vk': network_1.vk,
                'ip': network_1.external_address,
                'node_type': 'masternode'
            },
            {
                'vk': Wallet().verifying_key,
                'ip': 'tcp://127.0.0.1:19001',
                'node_type': 'masternode'
            },
            {
                'vk': Wallet().verifying_key,
                'ip': 'tcp://127.0.0.1:19002',
                'node_type': 'delegate'
            },
            {
                'vk': Wallet().verifying_key,
                'ip': 'tcp://127.0.0.1:19003',
                'node_type': 'delegate'
            },
        ]

        for node in node_list:
            vk = node.get('vk')

            self.add_vk_to_smartcontract(node_type=node.get('node_type'), network=network_1, vk=vk)
            network_1.create_peer(vk=vk, ip=node.get('ip'))

        network_map = network_1.make_network_map()

        self.assertEqual(2, len(network_map.get('masternodes')))
        self.assertEqual(2, len(network_map.get('delegates')))

        for node in node_list:
            node_type = node.get('node_type')
            vk = node.get('vk')
            ip = node.get('ip')
            self.assertEqual(ip, network_map[f'{node_type}s'][vk])

    def test_METHOD_network_map_to_node_list(self):
        network_1 = self.create_network()

        node_list = [
            {
                'vk': network_1.vk,
                'ip': network_1.external_address,
                'node_type': 'masternode'
            },
            {
                'vk': Wallet().verifying_key,
                'ip': 'tcp://127.0.0.1:19001',
                'node_type': 'masternode'
            },
            {
                'vk': Wallet().verifying_key,
                'ip': 'tcp://127.0.0.1:19002',
                'node_type': 'delegate'
            },
            {
                'vk': Wallet().verifying_key,
                'ip': 'tcp://127.0.0.1:19003',
                'node_type': 'delegate'
            },
        ]

        for node in node_list:
            vk = node.get('vk')

            self.add_vk_to_smartcontract(node_type=node.get('node_type'), network=network_1, vk=vk)
            network_1.create_peer(vk=vk, ip=node.get('ip'))

        network_map = network_1.make_network_map()

        node_list_from_netwrok_map = network_1.network_map_to_node_list(network_map=network_map)

        for node in node_list_from_netwrok_map:
            self.assertTrue(node in node_list)

    def test_METHOD_network_map_to_constitution(self):
        network_1 = self.create_network()

        node_list = [
            {
                'vk': network_1.vk,
                'ip': network_1.external_address,
                'node_type': 'masternode'
            },
            {
                'vk': Wallet().verifying_key,
                'ip': 'tcp://127.0.0.1:19001',
                'node_type': 'masternode'
            },
            {
                'vk': Wallet().verifying_key,
                'ip': 'tcp://127.0.0.1:19002',
                'node_type': 'delegate'
            },
            {
                'vk': Wallet().verifying_key,
                'ip': 'tcp://127.0.0.1:19003',
                'node_type': 'delegate'
            },
        ]

        for node in node_list:
            vk = node.get('vk')

            self.add_vk_to_smartcontract(node_type=node.get('node_type'), network=network_1, vk=vk)
            network_1.create_peer(vk=vk, ip=node.get('ip'))

        network_map = network_1.make_network_map()

        constitution_from_network_map = network_1.network_map_to_constitution(network_map=network_map)

        for node in node_list:
            node_type = node.get('node_type')
            vk = node.get('vk')
            self.assertTrue( vk in constitution_from_network_map[f'{node_type}s'])

        self.assertEqual(2, len(constitution_from_network_map['masternodes']))
        self.assertEqual(2, len(constitution_from_network_map['delegates']))

    def test_METHOD_connected_to_all_peers__task_completes_when_all_peers_are_connected(self):
        network_1 = self.create_network()

        peer_vk_1 = Wallet().verifying_key
        peer_vk_2 = Wallet().verifying_key

        network_1.create_peer(vk=peer_vk_1, ip='tcp://127.0.0.1:19001')
        network_1.create_peer(vk=peer_vk_2, ip='tcp://127.0.0.1:19002')

        task = asyncio.ensure_future(network_1.connected_to_all_peers())

        self.async_sleep(2)
        self.assertFalse(task.done())

        for peer in network_1.peers.values():
            peer.connected = True

        self.async_sleep(10)

        self.assertTrue(task.done())

    def test_METHOD_connected_to_peer_callback__returns_if_peer_is_None(self):
        network_1 = self.create_network()

        peer_vk = Wallet().verifying_key

        try:
            network_1.connected_to_peer_callback(peer_vk=peer_vk)
        except:
            self.fail("Calling remove_peer when peer doesn't exists should cause no exceptions.")

    def test_METHOD_connected_to_peer_callback__publishes_new_peer_connection(self):
        network_1 = self.create_network()

        network_1.setup_publisher()
        network_1.publisher.announce_new_peer_connection = self.mock_announce_new_peer_connection

        peer_vk = Wallet().verifying_key
        peer_ip = 'tcp://127.0.0.1:19001'

        network_1.create_peer(vk=peer_vk, ip=peer_ip)

        network_1.connected_to_peer_callback(peer_vk=peer_vk)

        self.assertEqual(peer_ip, self.publish_info[0])
        self.assertEqual(peer_vk, self.publish_info[1])


    def test_METHOD_new_peer_connection_service__calls_connect_peer_with_proper_info(self):
        network_1 = self.create_network()

        network_1.connect_peer = self.mock_connect_peer

        peer_vk = Wallet().verifying_key
        peer_ip = 'tcp://127.0.0.1:19001'

        network_1.new_peer_connection_service(msg={
            'ip': peer_ip,
            'vk': peer_vk
        })

        self.assertEqual(peer_ip, self.connect_info[0])
        self.assertEqual(peer_vk, self.connect_info[1])

    def test_METHOD_new_peer_connection_service__returns_if_message_does_not_have_vk(self):
        network_1 = self.create_network()

        network_1.connect_peer = self.mock_connect_peer

        peer_ip = 'tcp://127.0.0.1:19001'

        network_1.new_peer_connection_service(msg={
            'ip': peer_ip
        })

        self.assertIsNone(self.connect_info)

    def test_METHOD_new_peer_connection_service__returns_if_vk_equals_network_vk(self):
        network_1 = self.create_network()

        network_1.connect_peer = self.mock_connect_peer

        peer_ip = 'tcp://127.0.0.1:19001'

        network_1.new_peer_connection_service(msg={
            'ip': peer_ip,
            'vk': network_1.vk
        })

        self.assertIsNone(self.connect_info)

    def test_METHOD_new_peer_connection_service__returns_if_message_does_not_have_ip(self):
        network_1 = self.create_network()

        network_1.connect_peer = self.mock_connect_peer

        peer_vk = Wallet().verifying_key
        network_1.new_peer_connection_service(msg={
            'vk': peer_vk
        })

        self.assertIsNone(self.connect_info)

    def test_METHOD_new_peer_connection_service__returns_is_message_is_not_dict_does_not_raise_errors(self):
        network_1 = self.create_network()

        network_1.connect_peer = self.mock_connect_peer

        try:
            network_1.new_peer_connection_service(msg=None)
        except:
            self.fail("Calling new_peer_connection_service when msg doesn't exists should cause no exceptions.")

        self.assertIsNone(self.connect_info)

    def test_METHOD_setup_event_loop__uses_existing_running_loop(self):
        network_1 = self.create_network()
        network_1.loop = None

        network_1.setup_event_loop()

        loop = asyncio.get_event_loop()
        loop.close()

        loop_closed = network_1.loop.is_closed()
        self.assertTrue(loop_closed)

        network_1.setup_event_loop()

    def test_METHOD_setup_event_loop__creates_new_loop_if_current_closed(self):
        network_1 = self.create_network()
        network_1.loop = None

        loop = asyncio.get_event_loop()
        loop.close()

        network_1.setup_event_loop()
        self.async_sleep(0.1)

        self.assertFalse(network_1.loop.is_closed())

    def test_METHOD_connect_peer__returns_if_vk_is_self(self):
        network_1 = self.create_network()

        try:
            network_1.connect_peer(ip='tcp://127.0.0.1:19001', vk=network_1.vk)
        except:
            self.fail("Calling connect_peer with its own vk does not cause an error.")

        self.assertEqual(0, network_1.num_of_peers())

    def test_METHOD_connect_peer__returns_if_vk_not_in_node_list(self):
        network_1 = self.create_network()

        peer_vk = Wallet().verifying_key

        try:
            network_1.connect_peer(ip='tcp://127.0.0.1:19001', vk=peer_vk)
        except:
            self.fail("Calling connect_peer with a vk not in the node list does not cause errors.")

        self.assertEqual(0, network_1.num_of_peers())

    def test_METHOD_connect_peer__calls_test_connection_if_peer_exists_with_same_ip(self):
        network_1 = self.create_network()

        peer_ip = 'tcp://127.0.0.1:19001'
        peer_vk = Wallet().verifying_key

        network_1.create_peer(ip=peer_ip, vk=peer_vk)

        peer = network_1.get_peer(vk=peer_vk)
        peer.update_ip = self.mock_peer_update_ip
        peer.test_connection = self.mock_peer_test_connection
        peer.running = True

        self.add_vk_to_smartcontract(node_type='masternode', network=network_1, vk=peer_vk)

        try:
            network_1.connect_peer(ip='tcp://127.0.0.1:19001', vk=peer_vk)
        except:
            self.fail("Calling connect_peer with existing peer vk causes no errors.")

        self.async_sleep(0.1)

        self.assertFalse(self.called_ip_update)
        self.assertTrue(self.called_test_connection)

        self.assertEqual(1, network_1.num_of_peers())


    def test_METHOD_connect_peer__calls_update_ip_if_peer_exists_with_different_ip(self):
        network_1 = self.create_network()

        peer_ip = 'tcp://127.0.0.1:19001'
        peer_new_ip = 'tcp://127.0.0.1:19002'
        peer_vk = Wallet().verifying_key

        network_1.create_peer(ip=peer_ip, vk=peer_vk)

        peer = network_1.get_peer(vk=peer_vk)
        peer.update_ip = self.mock_peer_update_ip
        peer.test_connection = self.mock_peer_test_connection
        peer.running = True

        self.add_vk_to_smartcontract(node_type='masternode', network=network_1, vk=peer_vk)

        try:
            network_1.connect_peer(ip='tcp://127.0.0.1:19002', vk=peer_vk)
        except:
            self.fail("Calling connect_peer with existing peer vk causes no errors.")

        self.async_sleep(0.1)

        self.assertEqual(peer_new_ip, self.called_ip_update)
        self.assertFalse(self.called_test_connection)

        self.assertEqual(1, network_1.num_of_peers())

    def test_METHOD_connect_peer__adds_peer_if_vk_doesnt_exist(self):
        network_1 = self.create_network()

        peer_vk = Wallet().verifying_key
        self.add_vk_to_smartcontract(node_type='masternode', network=network_1, vk=peer_vk)

        try:
            network_1.connect_peer(ip='tcp://127.0.0.1:19001', vk=peer_vk)
            self.async_sleep(0.1)
        except:
            self.fail("Calling connect_peer with existing peer vk causes no errors.")

        self.assertEqual(1, network_1.num_of_peers())

        peer = network_1.get_peer(vk=peer_vk)
        self.assertIsNotNone(peer.verify_task)

    def test_METHOD_connect_bootnode__adds_peer_even_if_not_isnt_voted_in(self):
        network_1 = self.create_network()

        peer_vk = Wallet().verifying_key

        try:
            network_1.connect_to_bootnode(ip='tcp://127.0.0.1:19001', vk=peer_vk)
            self.async_sleep(0.1)
        except:
            self.fail("Calling connect_peer with existing peer vk causes no errors.")

        self.assertEqual(1, network_1.num_of_peers())

        peer = network_1.get_peer(vk=peer_vk)
        self.assertIsNotNone(peer.verify_task)

    def test_METHOD_hello_response_creates_properly_formatted_response(self):
        network_1 = self.create_network()

        challenge = 'testing'

        hello_response = network_1.hello_response(challenge=challenge)

        self.assertIsInstance(hello_response, str)

        hello_obj = json.loads(hello_response)
        self.assertEqual(ACTION_HELLO, hello_obj.get("response"))
        self.assertEqual(0, hello_obj.get("latest_block_number"))
        self.assertEqual("0", hello_obj.get("latest_hlc_timestamp"))
        self.assertEqual(network_1.wallet.sign(challenge), hello_obj.get("challenge_response"))

    def test_METHOD_hello_response_ignores_empty_challenge_arg(self):
        network_1 = self.create_network()

        hello_response = network_1.hello_response()

        self.assertIsInstance(hello_response, str)

        hello_obj = json.loads(hello_response)
        self.assertEqual(ACTION_HELLO, hello_obj.get("response"))
        self.assertEqual(0, hello_obj.get("latest_block_number"))
        self.assertEqual("0", hello_obj.get("latest_hlc_timestamp"))
        self.assertEqual("", hello_obj.get("challenge_response"))

    def test_METHOD_get_masternode_vks(self):
        network_1 = self.create_network()

        vks = [Wallet().verifying_key, Wallet().verifying_key]

        network_1.driver.driver.set(
            key="masternodes.S:members",
            value=vks
        )

        masternode_vks = network_1.get_masternode_vk_list()

        self.assertEqual(vks, masternode_vks)

    def test_METHOD_get_delegate_vks(self):
        network_1 = self.create_network()

        vks = [Wallet().verifying_key, Wallet().verifying_key]

        network_1.driver.driver.set(
            key="delegates.S:members",
            value=vks
        )

        masternode_vks = network_1.get_delegate_vk_list()

        self.assertEqual(vks, masternode_vks)

    def test_METHOD_get_masternode_and_delegate_vks(self):
        network_1 = self.create_network()

        masternode_vks = [Wallet().verifying_key, Wallet().verifying_key]
        delegate_vks = [Wallet().verifying_key, Wallet().verifying_key]

        network_1.driver.driver.set(
            key="masternodes.S:members",
            value=masternode_vks
        )

        network_1.driver.driver.set(
            key="delegates.S:members",
            value=delegate_vks
        )

        masternode_and_delegate_vks = network_1.get_masternode_and_delegate_vk_list()

        self.assertEqual(masternode_and_delegate_vks, masternode_vks + delegate_vks)

    def test_METHOD_map_vk_to_ip__creates_dict_with_correct_info(self):
        network_1 = self.create_network()

        peer_1 = ('tcp://127.0.0.1:19001', Wallet().verifying_key)
        peer_2 = ('tcp://127.0.0.1:19002', Wallet().verifying_key)

        network_1.create_peer(ip=peer_1[0], vk=peer_1[1])
        network_1.create_peer(ip=peer_2[0], vk=peer_2[1])

        vk_list = [peer_1[1], peer_2[1]]

        vk_to_ip_map = network_1.map_vk_to_ip(vk_list=vk_list)

        self.assertEqual(peer_1[0], vk_to_ip_map[peer_1[1]])
        self.assertEqual(peer_2[0], vk_to_ip_map[peer_2[1]])

    def test_METHOD_make_constitution(self):
        network_1 = self.create_network()

        masternode_1 = (network_1.router_address, network_1.vk)
        masternode_2 = ('tcp://127.0.0.1:19001', Wallet().verifying_key)
        masternode_3 = ('tcp://127.0.0.1:19002', Wallet().verifying_key)
        delegate_1 = ('tcp://127.0.0.1:19003', Wallet().verifying_key)
        delegate_2 = ('tcp://127.0.0.1:19004', Wallet().verifying_key)

        masternode_vks = [masternode_1[1], masternode_2[1], masternode_3[1]]
        delegate_vks = [delegate_1[1], delegate_2[1]]

        network_1.driver.driver.set(
            key="masternodes.S:members",
            value=masternode_vks
        )

        network_1.driver.driver.set(
            key="delegates.S:members",
            value=delegate_vks
        )

        network_1.create_peer(ip=masternode_1[0], vk=masternode_1[1])
        network_1.create_peer(ip=masternode_2[0], vk=masternode_2[1])
        network_1.create_peer(ip=masternode_3[0], vk=masternode_3[1])
        network_1.create_peer(ip=delegate_1[0], vk=delegate_1[1])
        network_1.create_peer(ip=delegate_2[0], vk=delegate_2[1])

        constitution = network_1.make_constitution()

        self.assertEqual(3, len(constitution.get('masternodes')))
        self.assertEqual(2, len(constitution.get('delegates')))

    def test_METHOD_get_peers_for_consensus(self):
        network_1 = self.create_network()

        masternode_1 = (network_1.router_address, network_1.vk)
        masternode_2 = ('tcp://127.0.0.1:19001', Wallet().verifying_key)
        masternode_3 = ('tcp://127.0.0.1:19002', Wallet().verifying_key)
        delegate_1 = ('tcp://127.0.0.1:19003', Wallet().verifying_key)
        delegate_2 = ('tcp://127.0.0.1:19004', Wallet().verifying_key)

        masternode_vks = [masternode_1[1], masternode_2[1], masternode_3[1]]
        delegate_vks = [delegate_1[1], delegate_2[1]]

        network_1.driver.driver.set(
            key="masternodes.S:members",
            value=masternode_vks
        )

        network_1.driver.driver.set(
            key="delegates.S:members",
            value=delegate_vks
        )

        consensus_peers = network_1.get_peers_for_consensus()

        self.assertEqual(4, len(consensus_peers))

    def test_METHOD_authorize_peer__can_add_peer_vk_to_cred_provider(self):
        network_1 = self.create_network()

        peer_wallet = Wallet()
        peer_vk = peer_wallet.verifying_key

        network_1.authorize_peer(peer_vk=peer_vk)

        self.assertTrue(network_1.router.cred_provider.key_is_approved(curve_vk=peer_wallet.curve_vk))

    def test_METHOD_revoke_peer_access__can_remove_a_peer_vk_from_cred_provider(self):
        network_1 = self.create_network()

        peer_wallet = Wallet()
        peer_vk = peer_wallet.verifying_key

        network_1.router.cred_provider.add_key(vk=peer_vk)
        self.assertTrue(network_1.router.cred_provider.key_is_approved(curve_vk=peer_wallet.curve_vk))

        network_1.revoke_peer_access(peer_vk=peer_vk)
        self.assertFalse(network_1.router.cred_provider.key_is_approved(curve_vk=peer_wallet.curve_vk))

    def test_METHOD_remove_peer__stops_and_deletes_peer_from_peers_dict(self):
        network_1 = self.create_network()

        peer_ip = 'tcp://127.0.0.1:19001'
        peer_vk = Wallet().verifying_key

        network_1.create_peer(ip=peer_ip, vk=peer_vk)

        peer = network_1.get_peer(vk=peer_vk)
        peer.connected = True
        peer.verified = True
        peer.running = True

        network_1.remove_peer(peer_vk=peer_vk)

        while network_1.get_peer(vk=peer_vk) is not None:
            self.async_sleep(0.1)

        self.assertIsNone(network_1.get_peer(vk=peer_vk))

    def test_METHOD_remove_peer__raises_no_exceptions_if_peer_does_not_exist(self):
        network_1 = self.create_network()

        peer_vk = Wallet().verifying_key

        try:
            network_1.remove_peer(peer_vk=peer_vk)
        except:
            self.fail('Calling remove_peer when peer does not exist should raise NO exceptions.')

        self.assertIsNone(network_1.get_peer(vk=peer_vk))

    def test_METHOD_stop_and_delete_peer__stops_and_deletes_peer_from_peers_dict(self):
        network_1 = self.create_network()

        peer_ip = 'tcp://127.0.0.1:19001'
        peer_vk = Wallet().verifying_key

        network_1.create_peer(ip=peer_ip, vk=peer_vk)

        peer = network_1.get_peer(vk=peer_vk)
        peer.connected = True
        peer.verified = True
        peer.running = True

        task = asyncio.ensure_future(network_1.stop_and_delete_peer(peer_vk=peer_vk))

        while not task.done():
            self.async_sleep(0.1)

        self.assertIsNone(network_1.get_peer(vk=peer_vk))

    def test_METHOD_stop_and_delete_peer__raises_no_exceptions_if_peer_does_not_exist(self):
        network_1 = self.create_network()

        peer_vk = Wallet().verifying_key

        try:
            task = asyncio.ensure_future(network_1.stop_and_delete_peer(peer_vk=peer_vk))
            loop = asyncio.get_event_loop()
            loop.run_until_complete(task)

        except:
            self.fail('Calling remove_peer when peer does not exist should raise NO exceptions.')

        self.assertIsNone(network_1.get_peer(vk=peer_vk))

    def test_METHOD_peer_is_voted_in__returns_TRUE_if_peer_is_in_smart_contract(self):
        network_1 = self.create_network()

        peer_vk = Wallet().verifying_key
        self.add_vk_to_smartcontract(node_type='masternode', network=network_1, vk=peer_vk)

        self.assertTrue(network_1.peer_is_voted_in(peer_vk))

    def test_METHOD_peer_is_voted_in__returns_FALSE_if_peer_is_not_in_smart_contract(self):
        network_1 = self.create_network()

        peer_vk = Wallet().verifying_key

        self.assertFalse(network_1.peer_is_voted_in(peer_vk))

    def test_METHOD_refresh_approved_peers_in_cred_provider__sets_cred_provicer_keys_to_what_is_in_smartcontracts(self):
        network_1 = self.create_network()

        # Add a key to the cred provider
        old_peer_wallet = Wallet()
        network_1.router.cred_provider.add_key(vk=old_peer_wallet.verifying_key)
        self.assertTrue(network_1.router.cred_provider.key_is_approved(curve_vk=old_peer_wallet.curve_vk))

        # Creates some new nodes that were voted in
        new_mn_wallet = Wallet()
        self.add_vk_to_smartcontract(node_type='masternode', network=network_1, vk=new_mn_wallet.verifying_key)

        new_del_wallet = Wallet()
        self.add_vk_to_smartcontract(node_type='delegate', network=network_1, vk=new_del_wallet.verifying_key)

        # Refresh the cred provider
        network_1.refresh_approved_peers_in_cred_provider()

        self.assertFalse(network_1.router.cred_provider.key_is_approved(curve_vk=old_peer_wallet.curve_vk))
        self.assertTrue(network_1.router.cred_provider.key_is_approved(curve_vk=new_mn_wallet.curve_vk))
        self.assertTrue(network_1.router.cred_provider.key_is_approved(curve_vk=new_del_wallet.curve_vk))

    def test_METHOD_refresh_peer_block_info(self):
        async def mock_send_request(msg_obj, timeout=1, retries=1):
            return {
                'response': LATEST_BLOCK_INFO,
                'latest_block_number': 10,
                'latest_hlc_timestamp': '10'
            }

        network_1 = self.create_network()

        peer_ip = 'tcp://127.0.0.1:19001'
        peer_vk = Wallet().verifying_key

        network_1.create_peer(ip=peer_ip, vk=peer_vk)

        peer = network_1.get_peer(vk=peer_vk)
        peer.connected = True
        peer.verified = True
        peer.running = True

        peer.send_request = mock_send_request

        task = asyncio.ensure_future(network_1.refresh_peer_block_info())

        while not task.done():
            self.async_sleep(1)

        self.assertEqual(10, peer.latest_block_number)
        self.assertEqual('10', peer.latest_block_hlc_timestamp)