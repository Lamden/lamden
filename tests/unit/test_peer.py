from lamden.peer import Peer
from lamden.crypto.wallet import Wallet
from contracting.db.driver import ContractDriver, InMemDriver

import unittest
import zmq
import zmq.asyncio

from lamden import storage
from pathlib import Path

from tests.unit.helpers.mock_publisher import MockPublisher
from tests.unit.helpers.mock_reply import MockReply
from tests.unit.helpers.mock_router import MockRouter

import asyncio
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

class TestSubscriberSocket(unittest.TestCase):
    def setUp(self):
        self.current_path = Path.cwd()
        self.ctx = zmq.asyncio.Context()

        self.server_wallet = Wallet()
        self.peer_wallet = Wallet()

        self.publisher_address = 'tcp://127.0.0.1:19000'
        self.direct_message_address = 'tcp://127.0.0.1:19001'

        self.ip = '127.0.0.1'

        self.peer = Peer(
            ip=self.ip,
            connected_callback=self.connected_callback,
            get_network_ip=self.get_network_ip,
            server_key=self.server_wallet.verifying_key,
            services={},
            wallet=self.peer_wallet
        )

        self.connected_callback_called = False

    def tearDown(self) -> None:
        if self.peer.running:
            self.peer.stop()
            del self.peer

    def connected_callback(self):
        self.connected_callback_called = True

    def get_network_ip(self):
        return 'tcp://127.0.0.1:19000'

    def test_can_create_instance__PEER(self):
        self.assertIsInstance(self.peer, Peer)

    def test_PROPERTY_vk(self):
        self.assertEqual(self.peer_wallet.verifying_key, self.peer.vk)

    def test_PROPERTY_ip(self):
        self.assertEqual(self.ip, self.peer.ip)

    def test_PROPERTY_is_running__return_FALSE_if_no_sockets_setup(self):
        self.assertFalse(self.peer.is_running)

    def test_PROPERTY_is_running__return_FALSE_if_no_subscriber_socket(self):
        self.peer.setup_request()
        self.assertFalse(self.peer.is_running)

    def test_PROPERTY_is_running__return_FALSE_if_no_request_socket(self):
        self.peer.setup_subscriber()
        self.assertFalse(self.peer.is_running)

    def test_PROPERTY_is_running__return_FALSE_if_sockets_exists_neither_running(self):
        self.peer.setup_subscriber()
        self.peer.setup_request()
        self.assertFalse(self.peer.is_running)

    def test_PROPERTY_is_running__return_FALSE_if_sockets_exists_subscriber_isnt_running(self):
        self.peer.setup_subscriber()
        self.peer.setup_request()
        self.peer.subscriber.running = False
        self.assertFalse(self.peer.is_running)

    def test_PROPERTY_is_running__return_FALSE_if_sockets_exists_request_isnt_running(self):
        self.peer.setup_subscriber()
        self.peer.setup_request()
        self.peer.request.running = False
        self.assertFalse(self.peer.is_running)

    def test_PROPERTY_is_running__return_TRUE_if_sockets_exists_and_all_running(self):
        self.peer.setup_subscriber()
        self.peer.setup_request()
        self.peer.request.running = True
        self.peer.subscriber.running = True
        self.assertTrue(self.peer.is_running)

    def test_PROPERTY_subscriber_address_returns_propertly_formatted_string(self):
        self.assertEqual('127.0.0.1', self.peer.ip)
        self.assertEqual(19000, self.peer.socket_ports['router'])
        self.assertEqual('tcp://127.0.0.1:19000', self.peer.request_address)

    def test_PROPERTY_subscriber_address_returns_propertly_formatted_string(self):
        self.assertEqual('127.0.0.1', self.peer.ip)
        self.assertEqual(19080, self.peer.socket_ports['publisher'])
        self.assertEqual('tcp://127.0.0.1:19080', self.peer.subscriber_address)

    def test_PROPERTY_lastest_block_number(self):
        latest_block_number = 100
        self.peer.set_latest_block_number(number=latest_block_number)
        self.assertEqual(latest_block_number, self.peer.latest_block_number)

    def test_PROPERTY_lastest_block_hlc_timestamp(self):
        hlc_timestamp = "1234"
        self.peer.set_latest_block_hlc_timestamp(hlc_timestamp=hlc_timestamp)

        self.assertEqual(hlc_timestamp, self.peer.latest_block_hlc_timestamp)

    def test_METHOD_calc_ports(self):
        self.peer.socket_ports['router'] = 19001
        self.peer.calc_ports()

        self.assertEqual(19001, self.peer.socket_ports['router'])
        self.assertEqual(19081, self.peer.socket_ports['publisher'])
        self.assertEqual(18081, self.peer.socket_ports['webserver'])

    def test_METHOD_set_ip__sets_from_hostname_no_port(self):
        self.peer.set_ip(address='tcp://127.0.0.2')
        self.assertEqual('127.0.0.2', self.peer.ip)

        self.assertEqual(19000, self.peer.socket_ports['router'])
        self.assertEqual(19080, self.peer.socket_ports['publisher'])
        self.assertEqual(18080, self.peer.socket_ports['webserver'])

    def test_METHOD_set_ip__sets_from_hostname_with_port(self):
        self.peer.set_ip(address='tcp://127.0.0.2:19001')

        self.assertEqual('127.0.0.2', self.peer.ip)
        self.assertEqual(19001, self.peer.socket_ports['router'])
        self.assertEqual(19081, self.peer.socket_ports['publisher'])
        self.assertEqual(18081, self.peer.socket_ports['webserver'])

    def test_METHOD_set_ip__sets_from_ip_and_port_with_no_protocol(self):
        self.peer.set_ip(address='127.0.0.2:19001')

        self.assertEqual('127.0.0.2', self.peer.ip)
        self.assertEqual(19001, self.peer.socket_ports['router'])
        self.assertEqual(19081, self.peer.socket_ports['publisher'])
        self.assertEqual(18081, self.peer.socket_ports['webserver'])

    def test_METHOD_set_ip__sets_from_ip_with_no_port_or_protocol(self):
        self.peer.set_ip(address='127.0.0.2')

        self.assertEqual('127.0.0.2', self.peer.ip)
        self.assertEqual(19000, self.peer.socket_ports['router'])
        self.assertEqual(19080, self.peer.socket_ports['publisher'])
        self.assertEqual(18080, self.peer.socket_ports['webserver'])

    def test_METHOD_set_driver(self):
        driver = ContractDriver(driver=InMemDriver())
        self.peer.set_driver(driver=driver)

        self.assertEqual(driver, self.peer.driver)

    def test_METHOD_set_storage(self):
        block_storage_path = Path(f'{self.current_path}/.lamden')
        storage.BlockStorage(home=block_storage_path)
        self.peer.set_storage(storage=storage)

        self.assertEqual(storage, self.peer.storage)

    def test_METHOD_set_latest_block_number(self):
        latest_block_number = 100
        self.peer.set_latest_block_number(number=latest_block_number)

        self.assertEqual(latest_block_number, self.peer.latest_block_info['number'])

    def test_METHOD_set_latest_block_hlc_timestamp(self):
        hlc_timestamp = "1234"
        self.peer.set_latest_block_hlc_timestamp(hlc_timestamp=hlc_timestamp)

        self.assertEqual(hlc_timestamp, self.peer.latest_block_info['hlc_timestamp'])