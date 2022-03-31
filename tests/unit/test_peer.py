import json

from lamden.peer import Peer
from lamden.sockets.request import Result
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
    @classmethod
    def setUpClass(cls) -> None:
        cls.ip = '127.0.0.1'

        cls.remote_peer_wallet = Wallet()
        cls.my_wallet = Wallet()

        cls.remote_peer = MockRouter(
            valid_peers=[cls.my_wallet.curve_vk],
            wallet=cls.remote_peer_wallet
        )

    def setUp(self):
        self.ctx = zmq.asyncio.Context()

        self.peer = Peer(
            ip=self.__class__.ip,
            connected_callback=self.connected_callback,
            get_network_ip=self.get_network_ip,
            server_key=self.__class__.remote_peer_wallet.curve_vk,
            services={},
            local_wallet=self.__class__.my_wallet
        )

        self.connected_callback_called = False

    def tearDown(self) -> None:
        if self.peer.running:
            self.peer.stop()
            del self.peer

            self.async_sleep(2)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.remote_peer.stop()
        cls.remote_peer.join()

    def connected_callback(self):
        self.connected_callback_called = True

    def get_network_ip(self):
        return 'tcp://127.0.0.1:19000'

    def await_sending_request(self, process, args={}):
        tasks = asyncio.gather(
            process(**args)
        )
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)
        return res[0]

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def test_can_create_instance_MOCKROUTER(self):
        self.assertIsInstance(obj=self.__class__.remote_peer, cls=MockRouter)

    def test_can_create_instance__PEER(self):
        self.assertIsInstance(self.peer, Peer)

    def test_PROPERTY_local_vk(self):
        self.assertEqual(self.my_wallet.verifying_key, self.peer.local_vk)

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

    def test_PROPERTY_is_connected__return_FALSE(self):
        self.assertFalse(self.peer.is_connected)

    def test_PROPERTY_is_connected__return_TRUE(self):
        self.peer.connected = True
        self.assertTrue(self.peer.is_connected)

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
        block_storage_path = Path(f'{Path.cwd()}/.lamden')
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

    def test_METHOD_is_available__returns_FALSE_request_cannot_ping(self):
        self.peer.setup_request()
        self.peer.socket_ports['router'] = 1000
        is_available = self.peer.is_available()
        self.assertFalse(is_available)

    def test_METHOD_is_available__returns_TRUE_if_peer_responds_to_ping(self):
        self.peer.setup_request()
        is_available = self.peer.is_available()
        self.assertTrue(is_available)

    def test_METHOD_ping__returns_successful_msg_if_peer_available(self):
        self.peer.setup_request()
        msg = self.await_sending_request(self.peer.ping)
        expected_result = {'action': 'ping', 'success': True}

        self.assertDictEqual(expected_result, msg)

    def test_METHOD_ping__returns_NONE_if_peer_unavailable(self):
        self.peer.setup_request()
        self.peer.socket_ports['router'] = 1000
        msg = self.await_sending_request(self.peer.ping)

        self.assertIsNone(msg)

    def test_METHOD_hello__returns_successful_msg_if_peer_available(self):
        self.peer.setup_request()
        msg = self.await_sending_request(self.peer.hello)
        expected_result = {'action': 'hello', 'ip': self.get_network_ip(), 'success': True}

        self.assertDictEqual(expected_result, msg)

    def test_METHOD_hello__returns_NONE_if_peer_unavailable(self):
        self.peer.setup_request()
        self.peer.socket_ports['router'] = 1000
        msg = self.await_sending_request(self.peer.ping)

        self.assertIsNone(msg)

    def test_METHOD_get_latest_block_info__returns_successful_msg_if_peer_available(self):
        self.peer.setup_request()
        msg = self.await_sending_request(self.peer.get_latest_block_info)
        expected_result = {'action': 'latest_block_info', 'success': True}

        self.assertDictEqual(expected_result, msg)

    def test_METHOD_get_latest_block_info__returns_NONE_if_peer_unavailable(self):
        self.peer.setup_request()
        self.peer.socket_ports['router'] = 1000
        msg = self.await_sending_request(self.peer.get_latest_block_info)

        self.assertIsNone(msg)

    def test_METHOD_get_block__returns_successful_msg_if_peer_available(self):
        self.peer.setup_request()
        msg = self.await_sending_request(process=self.peer.get_block, args={'block_num': 100})
        expected_result = {'action': 'get_block', 'block_num': 100, 'success': True}

        self.assertDictEqual(expected_result, msg)

    def test_METHOD_get_block__returns_NONE_if_peer_unavailable(self):
        self.peer.setup_request()
        self.peer.socket_ports['router'] = 1000
        msg = self.await_sending_request(process=self.peer.get_block, args={'block_num': 100})

        self.assertIsNone(msg)

    def test_METHOD_get_node_list__returns_successful_msg_if_peer_available(self):
        self.peer.setup_request()
        msg = self.await_sending_request(process=self.peer.get_node_list)
        expected_result = {'action': 'get_node_list', 'success': True}

        self.assertDictEqual(expected_result, msg)

    def test_METHOD_get_node_list__returns_NONE_if_peer_unavailable(self):
        self.peer.setup_request()
        self.peer.socket_ports['router'] = 1000
        msg = self.await_sending_request(self.peer.get_node_list)

        self.assertIsNone(msg)

    def test_METHOD_send_request__result_returns_successful_msg_if_peer_available(self):
        self.peer.setup_request()
        msg = self.await_sending_request(process=self.peer.send_request, args={
            'msg_obj': {'action': 'test_send'}
        })
        expected_result = {'action': 'test_send', 'success': True}

        self.assertDictEqual(expected_result, msg)

    def test_METHOD_send_request__result_returns_NONE_if_peer_unavailable(self):
        self.peer.setup_request()
        self.peer.socket_ports['router'] = 1000
        msg = self.await_sending_request(process=self.peer.send_request, args={
            'msg_obj': {'action': 'test_send'}
        })

        self.assertIsNone(msg)

    def test_METHOD_send_request__can_send_multiple_messages_in_succession(self):
        self.peer.setup_request()
        expected_result = {'action': 'test_send', 'success': True}

        for i in range(5):
            msg = self.await_sending_request(process=self.peer.send_request, args={
                'msg_obj': {'action': 'test_send'}
            })

            self.assertDictEqual(expected_result, msg)

    def test_METHOD_send_request__can_send_multiple_messages_at_once(self):
        self.peer.setup_request()
        tasks = asyncio.gather(
            self.peer.send_request(msg_obj={'action': 'test_send'}),
            self.peer.send_request(msg_obj={'action': 'test_send'}),
            self.peer.send_request(msg_obj={'action': 'test_send'}),
            self.peer.send_request(msg_obj={'action': 'test_send'}),
            self.peer.send_request(msg_obj={'action': 'test_send'})
        )
        loop = asyncio.get_event_loop()
        messages = loop.run_until_complete(tasks)

        expected_result = {'action': 'test_send', 'success': True}

        for i in range(2):
            self.assertDictEqual(expected_result, messages[i])

    def test_METHOD_handle_result__adds_success_TRUE_attribute_to_msg(self):
        result = Result(success=True, response=json.dumps({}).encode('UTF-8'))
        msg = self.peer.handle_result(result=result)

        self.assertTrue(msg.get('success'))

    def test_METHOD_handle_result__returns_None_if_success_is_FALSE(self):
        result = Result(success=False, response=json.dumps({}).encode('UTF-8'))
        msg = self.peer.handle_result(result=result)

        self.assertIsNone(msg)

    def test_METHOD_handle_result__returns_None_if_success_is_FALSE(self):
        result = Result(success=False, response=json.dumps({}).encode('UTF-8'))
        msg = self.peer.handle_result(result=result)

        self.assertIsNone(msg)