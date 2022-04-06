import json

from lamden.peer import Peer
from lamden.sockets.request import Request, Result
from lamden.sockets.subscriber import Subscriber
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

class MockService():
    def __init__(self, callback):
        self.callback = callback

    async def process_message(self, msg):
        self.callback(msg)


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
            get_network_ip=self.get_network_ip,
            server_vk=self.__class__.remote_peer_wallet.verifying_key,
            services=self.get_services,
            local_wallet=self.__class__.my_wallet
        )

        self.services = {}

        self.connected_callback_called = False
        self.reconnect_called = False
        self.service_callback_data = None

    def tearDown(self) -> None:
        self.peer.stop()
        del self.peer

    @classmethod
    def tearDownClass(cls) -> None:
        cls.remote_peer.stop()
        cls.remote_peer.join()

    def connected_callback(self, vk):
        self.connected_callback_called = vk

    def reconnect(self):
        self.reconnect_called = True

    def get_services(self):
        return self.services

    def get_network_ip(self):
        return 'tcp://127.0.0.1:19000'

    def service_callback(self, msg):
        self.service_callback_data = msg

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

    def test_PROPERTY_ip__returns_NONE_if_no_url_set(self):
        self.peer.url = None
        self.assertIsNone(self.peer.ip)

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

    def test_PROPERTY_is_verified__return_FALSE(self):
        self.assertFalse(self.peer.is_verified)

    def test_PROPERTY_is_verified__return_TRUE(self):
        self.peer.verified = True
        self.assertTrue(self.peer.is_verified)

    def test_PROPERTY_subscriber_address_returns_propertly_formatted_string(self):
        self.assertEqual('127.0.0.1', self.peer.ip)
        self.assertEqual(19000, self.peer.socket_ports['router'])
        self.assertEqual('tcp://127.0.0.1:19000', self.peer.request_address)

    def test_PROPERTY_subscriber_address_returns_propertly_formatted_string(self):
        self.assertEqual('127.0.0.1', self.peer.ip)
        self.assertEqual(19080, self.peer.socket_ports['publisher'])
        self.assertEqual('tcp://127.0.0.1:19080', self.peer.subscriber_address)

    def test_PROPERTY_latest_block_number(self):
        latest_block_number = 100
        self.peer.set_latest_block_number(number=latest_block_number)
        self.assertEqual(latest_block_number, self.peer.latest_block_number)

    def test_PROPERTY_latest_block_hlc_timestamp(self):
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
        expected_result = {'response': 'hello', 'success': True}

        self.assertDictEqual(expected_result, msg)

    def test_METHOD_hello__returns_NONE_if_peer_unavailable(self):
        self.peer.setup_request()
        self.peer.socket_ports['router'] = 1000
        msg = self.await_sending_request(self.peer.ping)

        self.assertIsNone(msg)

    def test_METHOD_get_latest_block_info__sets_peer_latest_block_info_after_successful_call(self):
        self.peer.setup_request()
        msg = self.await_sending_request(self.peer.get_latest_block_info)

        block_num = 100
        hlc_timestamp = '1234'

        expected_result = {
            'response': 'latest_block_info',
            'latest_block_number': block_num,
            'latest_hlc_timestamp': hlc_timestamp,
            'success': True
        }

        self.assertDictEqual(expected_result, msg)
        self.assertEqual(block_num, self.peer.latest_block_number)
        self.assertEqual(hlc_timestamp, self.peer.latest_block_hlc_timestamp)

    def test_METHOD_get_latest_block_info__doesnot_set_peer_latest_block_info_after_unsuccessful_call(self):
        self.peer.setup_request()
        self.peer.socket_ports['router'] = 1000

        msg = self.await_sending_request(self.peer.get_latest_block_info)
        self.assertIsNone(msg)

        self.assertEqual(0, self.peer.latest_block_info.get('number'))
        self.assertEqual('0', self.peer.latest_block_info.get('hlc_timestamp'))

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

    def test_METHOD_send_request__returns_None_if_msg_is_None(self):
        self.peer.setup_request()

        msg = self.await_sending_request(process=self.peer.send_request, args={
            'msg_obj': None
        })

        self.assertIsNone(msg)

    def test_METHOD_send_request__returns_None_if_msg_is_not_json_serializable(self):
        self.peer.setup_request()

        msg = self.await_sending_request(process=self.peer.send_request, args={
            'msg_obj': json.dumps({'testing':True}).encode('UTF-8')
        })

        self.assertIsNone(msg)

    def test_METHOD_send_request__raises_error_if_request_not_initialized(self):
        msg = None
        with self.assertRaises(AttributeError) as error:
            msg = self.await_sending_request(process=self.peer.send_request, args={'msg_obj': {}})

        self.assertIsNone(msg)
        self.assertEqual("Request socket not setup.", str(error.exception))

    def test_METHOD_send_resquest__returns_None_if_mesage_not_json_serializable(self):
        self.peer.setup_request()
        msg = self.await_sending_request(process=self.peer.send_request, args={'msg_obj': None})

        self.assertIsNone(msg)

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

    def test_METHOD_handle_result__sets_connected_to_TRUE_if_successful_request(self):
        self.peer.setup_request()
        self.peer.connected = False
        result = Result(success=True, response=json.dumps({}).encode('UTF-8'))
        self.peer.handle_result(result=result)

        self.assertTrue(self.peer.is_connected)

    def test_METHOD_handle_result__sets_connected_to_FALSE_if_unsuccessful_request(self):
        self.peer.setup_request()
        self.peer.connected = True
        result = Result(success=False, response=json.dumps({}).encode('UTF-8'))
        self.peer.handle_result(result=result)

        self.assertFalse(self.peer.is_connected)

    def test_METHOD_handle_result__calls_reconnect_on_self_if_unsuccessful_request(self):
        self.peer.setup_request()
        self.peer.reconnect = self.reconnect
        result = Result(success=False, response=json.dumps({}).encode('UTF-8'))
        self.peer.handle_result(result=result)

        self.assertTrue(self.reconnect_called)

    def test_METHOD_handle_result__does_not_call_reconnect_on_self_if_successful_request(self):
        self.peer.setup_request()
        self.peer.reconnect = self.reconnect
        result = Result(success=True, response=json.dumps({}).encode('UTF-8'))
        self.peer.handle_result(result=result)

        self.assertFalse(self.reconnect_called)

    def test_METHOD_handle_result__returns_NONE_if_response_is_not_bytes(self):
        self.peer.setup_request()
        self.peer.reconnect = self.reconnect
        result = Result(success=True, response={})
        res = self.peer.handle_result(result=result)

        self.assertIsNone(res)

    def test_METHOD_reconnect_loop__loops_until_peer_is_available(self):
        self.peer.setup_request()
        self.peer.running = True
        self.peer.socket_ports['router'] = 1000

        asyncio.ensure_future(self.peer.reconnect_loop())

        self.async_sleep(2)
        self.assertTrue(self.peer.reconnecting)
        self.assertFalse(self.peer.connected)

        self.peer.socket_ports['router'] = 19000

        self.async_sleep(2)

        self.assertTrue(self.peer.connected)
        self.assertFalse(self.peer.reconnecting)


    def test_METHOD_reconnect_loop__sets_peer_as_connected_once_successful(self):
        self.peer.setup_request()
        self.peer.connected = False
        self.peer.reconnecting = False
        self.peer.running = True

        tasks = asyncio.gather(
            self.peer.reconnect_loop()
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        self.assertTrue(self.peer.connected)
        self.assertFalse(self.peer.reconnecting)

    def test_METHOD_reconnect_loop__loop_exits_if_peer_set_to_running_FALSE(self):
        self.peer.setup_request()
        self.peer.running = True
        self.peer.socket_ports['router'] = 1000

        asyncio.ensure_future(self.peer.reconnect_loop())

        self.async_sleep(1)
        self.peer.running = False
        self.async_sleep(1)

        self.assertFalse(self.peer.reconnecting)
        self.assertFalse(self.peer.connected)

    def test_METHOD_reconnect_loop__exits_if_already_reconnecting(self):
        self.peer.setup_request()
        self.peer.reconnecting = True
        self.peer.connected = False

        tasks = asyncio.gather(
            self.peer.reconnect_loop()
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        self.assertTrue(self.peer.reconnecting)
        self.assertFalse(self.peer.connected)

    def test_METHOD_setup_subscriber(self):
        self.peer.setup_subscriber()
        self.assertIsInstance(self.peer.subscriber, Subscriber)

    def test_METHOD_setup_request(self):
        self.peer.setup_request()
        self.assertIsInstance(self.peer.request, Request)

    def test_METHOD_stop__stops_subscriber(self):
        self.peer.setup_subscriber()
        self.async_sleep(2)
        self.assertTrue(self.peer.subscriber.is_running)
        self.peer.stop()
        self.assertFalse(self.peer.subscriber.is_running)

    def test_METHOD_stop__stops_request(self):
        self.peer.setup_request()
        self.assertTrue(self.peer.request.is_running)
        self.peer.stop()
        self.assertFalse(self.peer.request.is_running)

    def test_METHOD_stop__stops_itself(self):
        self.peer.setup_request()
        self.peer.running = True

        self.peer.stop()
        self.assertFalse(self.peer.running)


    def test_METHOD_store_latest_block_info__stores_if_both_have_values(self):
        latest_block_num = 50
        latest_hlc_timestamp = '1234'
        self.peer.store_latest_block_info(
                latest_block_num=latest_block_num,
                latest_hlc_timestamp=latest_hlc_timestamp
            )

        self.assertEqual(latest_block_num, self.peer.latest_block_info.get('number'))
        self.assertEqual(latest_hlc_timestamp, self.peer.latest_block_info.get('hlc_timestamp'))

    def test_METHOD_store_latest_block_info__does_not_store_anything_if_number_is_not_INT(self):
        latest_block_num = None
        latest_hlc_timestamp = '1234'
        self.peer.store_latest_block_info(
                latest_block_num=latest_block_num,
                latest_hlc_timestamp=latest_hlc_timestamp
            )

        self.assertEqual(0, self.peer.latest_block_info.get('number'))
        self.assertEqual('0', self.peer.latest_block_info.get('hlc_timestamp'))

    def test_METHOD_store_latest_block_info__does_not_store_anything_if_hlc_timestamp_is_not_STR(self):
        latest_block_num = 50,
        latest_hlc_timestamp = None
        self.peer.store_latest_block_info(
                latest_block_num=latest_block_num,
                latest_hlc_timestamp=latest_hlc_timestamp
            )

        self.assertEqual(0, self.peer.latest_block_info.get('number'))
        self.assertEqual('0', self.peer.latest_block_info.get('hlc_timestamp'))

    def test_METHOD_start__creates_request_socket(self):
        self.peer.start()

        self.assertIsNotNone(self.peer.request)

    def test_METHOD_start__creates_subscriber_socket(self):
        self.peer.start()
        self.async_sleep(4)

        self.assertIsNotNone(self.peer.subscriber)

    def test_METHOD_start__sets_running_to_TRUE(self):
        self.peer.start()
        self.assertTrue(self.peer.running)

    def test_METHOD_start__sets_peer_is_running_to_TRUE(self):
        self.peer.start()
        self.async_sleep(2)
        self.assertTrue(self.peer.is_running)

    def test_METHOD_start__exits_if_already_running(self):
        self.peer.running = True
        self.peer.verified = False
        self.peer.start()
        self.async_sleep(2)
        self.assertFalse(self.peer.is_verified)

    def test_METHOD_validate_peer__sets_verified_when_peer_exists(self):
        self.peer.setup_request()
        tasks = asyncio.gather(
            self.peer.verify_peer()
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        self.assertTrue(self.peer.is_verified)

    def test_METHOD_validate_peer__calls_connected_callback_if_exists_and_passes_vk(self):
        self.peer.setup_request()
        self.peer.connected_callback = self.connected_callback
        tasks = asyncio.gather(
            self.peer.verify_peer()
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        self.assertEqual(self.peer.local_vk, self.connected_callback_called)

    def test_METHOD_validate_peer__starts_subscriber(self):
        self.peer.setup_request()

        tasks = asyncio.gather(
            self.peer.verify_peer()
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        self.async_sleep(2)
        self.assertIsNotNone(self.peer.subscriber)
        self.assertTrue(self.peer.subscriber.is_running)

    def test_METHOD_validate_peer__bubbles_AttributeError_if_socket_not_setup(self):
        with self.assertRaises(AttributeError) as error:
            tasks = asyncio.gather(
                self.peer.verify_peer()
            )
            loop = asyncio.get_event_loop()
            loop.run_until_complete(tasks)

        self.assertEqual("Request socket not setup.", str(error.exception))
        self.assertFalse(self.peer.is_verified)

    def test_METHOD_validate_peer__verified_remains_FALSE_if_peer_unresponsive(self):
        self.peer.setup_request()
        self.peer.socket_ports['router'] = 1000

        tasks = asyncio.gather(
            self.peer.verify_peer()
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        self.assertFalse(self.peer.is_verified)

    def test_METHOD_validate_peer_loop__sets_peer_is_verified(self):
        self.peer.setup_request()
        self.peer.running = True

        tasks = asyncio.gather(
            self.peer.verify_peer_loop()
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        self.assertTrue(self.peer.is_verified)

    def test_METHOD_set_latest_block_number__sets_int(self):
        self.peer.set_latest_block_number(number=100)
        self.assertEqual(100, self.peer.latest_block_number)

    def test_METHOD_set_latest_block_number__ignores_non_int_values(self):
        self.peer.set_latest_block_number(number='100')
        self.assertEqual(0, self.peer.latest_block_number)

    def test_METHOD_set_latest_block_hlc_timestamp__sets_str(self):
        self.peer.set_latest_block_hlc_timestamp(hlc_timestamp='1234')
        self.assertEqual('1234', self.peer.latest_block_hlc_timestamp)

    def test_METHOD_set_latest_block_hlc_timestamp__ignores_non_str_values(self):
        self.peer.set_latest_block_hlc_timestamp(hlc_timestamp=100)
        self.assertEqual('0', self.peer.latest_block_hlc_timestamp)

    def test_METHOD_set_latest_block_info__sets_when_both_values_correct_type(self):
        self.peer.set_latest_block_info(number=100, hlc_timestamp='1234')
        self.assertEqual(100, self.peer.latest_block_number)
        self.assertEqual('1234', self.peer.latest_block_hlc_timestamp)

    def test_METHOD_set_latest_block_info__does_not_set_either_when_number_not_int(self):
        self.peer.set_latest_block_info(number='100', hlc_timestamp='1234')
        self.assertEqual(0, self.peer.latest_block_number)
        self.assertEqual('0', self.peer.latest_block_hlc_timestamp)

    def test_METHOD_set_latest_block_info__does_not_set_either_when_hlc_timestamp_not_str(self):
        self.peer.set_latest_block_info(number='100', hlc_timestamp=1234)
        self.assertEqual(0, self.peer.latest_block_number)
        self.assertEqual('0', self.peer.latest_block_hlc_timestamp)

    def test_METHOD_process_subscription__calls_appropriate_service_based_on_topic(self):
        self.services = {
            'testing': MockService(callback=self.service_callback)
        }
        data = {'testing': True}

        tasks = asyncio.gather(
            self.peer.process_subscription(data=['testing'.encode('UTF-8'),json.dumps(data).encode('UTF-8')])
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        self.assertEqual(data, self.service_callback_data)

    def test_METHOD_process_subscription__does_nothing_if_service_does_not_exist(self):
        data = {'testing': True}

        try:
            tasks = asyncio.gather(
                self.peer.process_subscription(data=['testing'.encode('UTF-8'), json.dumps(data).encode('UTF-8')])
            )
            loop = asyncio.get_event_loop()
            loop.run_until_complete(tasks)
        except Exception as err:
            print(err)
            self.fail("Should not raise exception if services does not exist!")

        self.assertIsNone(self.service_callback_data)

    def test_METHOD_process_subscription__doesnt_bubble_ValueError_for_bad_messages(self):
        try:
            tasks = asyncio.gather(
                self.peer.process_subscription(data=['testing'.encode('UTF-8')])
            )
            loop = asyncio.get_event_loop()
            loop.run_until_complete(tasks)
        except ValueError as err:
            print(err)
            self.fail("Should not raise ValueError!")

    def test_METHOD_process_subscription__doesnt_bubble_on_bad_message_decoding(self):
        try:
            tasks = asyncio.gather(
                self.peer.process_subscription(data=['testing'.encode('UTF-8'), None])
            )
            loop = asyncio.get_event_loop()
            loop.run_until_complete(tasks)
        except Exception as err:
            print(err)
            self.fail("Should not raise Error on bad data package!")

    def test_METHOD_process_subscription__rasies_AttributeError_if_services_is_None(self):
        self.peer.services = None
        with self.assertRaises(AttributeError) as error:
            tasks = asyncio.gather(
                self.peer.process_subscription(data=[])
            )
            loop = asyncio.get_event_loop()
            loop.run_until_complete(tasks)

        expected_error = "Cannot process subscription messages, services not setup."
        self.assertEqual(expected_error, str(error.exception))



