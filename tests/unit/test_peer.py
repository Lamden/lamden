import json

from lamden.peer import Peer
from lamden.sockets.request import Request, Result
from lamden.sockets.subscriber import Subscriber
from lamden.crypto.wallet import Wallet
from contracting.db.driver import ContractDriver, InMemDriver

import unittest
import zmq
import zmq.asyncio

from tests.unit.helpers.mock_router import MockRouter

import asyncio
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

class MockService():
    def __init__(self, callback):
        self.callback = callback

    async def process_message(self, msg):
        self.callback(msg)


class TestPeer(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ip = '127.0.0.1'

        cls.remote_peer_wallet = Wallet()
        cls.local_wallet = Wallet()

        cls.remote_peer = MockRouter(
            valid_peers=[cls.local_wallet.curve_vk],
            wallet=cls.remote_peer_wallet
        )


    def setUp(self):
        self.ctx = zmq.asyncio.Context()

        self.remote_peer = self.__class__.remote_peer
        self.remote_peer_wallet = self.__class__.remote_peer_wallet
        self.local_wallet = self.__class__.local_wallet

        self.peer_vk = self.remote_peer_wallet.verifying_key

        self.peer = Peer(
            ip=self.__class__.ip,
            get_network_ip=self.get_network_ip,
            server_vk=self.peer_vk,
            services=self.get_services,
            local_wallet=self.local_wallet
        )

        self.services = {}

        self.connected_callback_called = False
        self.reconnect_called = False
        self.service_callback_data = None

    def tearDown(self) -> None:
        task = asyncio.ensure_future(self.peer.stop())
        while not task.done():
            self.async_sleep(0.1)

        del self.peer

    @classmethod
    def tearDownClass(cls) -> None:
        if  cls.remote_peer:
            cls.remote_peer.stop()
            cls.remote_peer.join()

    def connected_callback(self, peer_vk):
        self.connected_callback_called = peer_vk

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
        self.assertEqual(self.remote_peer_wallet.curve_vk, self.peer.server_curve_vk)

    def test_can_create_instance__creates_server_curve_vk_from_verifying_key(self):
        self.assertIsInstance(self.peer, Peer)

    def test_METHOD_setup_event_loop__uses_existing_running_loop(self):
        peer = Peer(
            ip=self.__class__.ip,
            get_network_ip=self.get_network_ip,
            server_vk=self.peer_vk,
            services=self.get_services,
            local_wallet=self.local_wallet
        )

        peer.loop = None

        peer.setup_event_loop()

        loop = asyncio.get_event_loop()
        loop.close()

        loop_closed = peer.loop.is_closed()
        self.assertTrue(loop_closed)

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def test_METHOD_setup_event_loop__creates_new_loop_if_current_closed(self):
        peer = Peer(
            ip=self.__class__.ip,
            get_network_ip=self.get_network_ip,
            server_vk=self.peer_vk,
            services=self.get_services,
            local_wallet=self.local_wallet
        )

        peer.loop = None

        loop = asyncio.get_event_loop()
        loop.close()

        peer.setup_event_loop()

        self.async_sleep(0.1)
        self.assertFalse(peer.loop.is_closed())

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def test_PROPERTY_local_vk(self):
        self.assertEqual(self.local_wallet.verifying_key, self.peer.local_vk)

    def test_PROPERTY_ip(self):
        self.assertEqual(self.ip, self.peer.ip)

    def test_PROPERTY_ip__returns_NONE_if_no_url_set(self):
        self.peer.url = None
        self.assertIsNone(self.peer.ip)

    def test_PROPERTY_is_running__return_True_if_running_is_True(self):
        self.peer.running = True
        self.assertTrue(self.peer.is_running)

    def test_PROPERTY_is_running__return_False_if_running_is_False(self):
        self.peer.running = False
        self.assertFalse(self.peer.is_running)

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

    def test_PROPERTY_is_verifying__returns_FALSE_if_None(self):
        self.assertIsNone(self.peer.verify_task)
        self.assertFalse(self.peer.is_verifying)

    def test_PROPERTY_is_verifying__returns_FALSE_if_verifying_task_is_Done(self):
        async def simple_task():
            self.async_sleep(0.01)

        self.peer.verify_task = asyncio.ensure_future(simple_task())

        while not self.peer.verify_task.done():
            self.async_sleep(0.015)

        self.assertTrue(self.peer.verify_task.done())
        self.assertFalse(self.peer.is_verifying)

    def test_PROPERTY_is_verifying__returns_True_if_verifying_task_is_NOT_Done(self):
        async def simple_task():
            self.async_sleep(0.1)

        self.peer.verify_task = asyncio.ensure_future(simple_task())

        self.assertFalse(self.peer.verify_task.done())
        self.assertTrue(self.peer.is_verifying)

        while not self.peer.verify_task.done():
            self.async_sleep(0)

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
        challenge = msg.get('challenge')

        self.assertIsInstance(msg.get('challenge'), str)
        expected_result = {
            'response': 'hello',
            'latest_block_number': 1,
            'latest_hlc_timestamp': '1',
            'success': True,
            'challenge': msg.get('challenge'),
            'challenge_response': self.remote_peer.wallet.sign(challenge)
        }

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

    def test_METHOD_get_network_map__returns_successful_msg_if_peer_available(self):
        self.peer.setup_request()
        msg = self.await_sending_request(process=self.peer.get_node_list)
        expected_result = {'action': 'get_network_map', 'success': True}

        self.assertDictEqual(expected_result, msg)

    def test_METHOD_get_network_map__returns_NONE_if_peer_unavailable(self):
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

        task = asyncio.ensure_future(self.peer.stop())
        while not task.done():
            self.async_sleep(0.1)

        self.assertFalse(self.peer.subscriber.is_running)

    def test_METHOD_stop__stops_request(self):
        self.peer.setup_request()
        self.assertTrue(self.peer.request.is_running)

        task = asyncio.ensure_future(self.peer.stop())
        while not task.done():
            self.async_sleep(0.1)

        self.assertFalse(self.peer.request.is_running)

    def test_METHOD_stop__stops_itself(self):
        self.peer.setup_request()
        self.peer.running = True

        task = asyncio.ensure_future(self.peer.stop())
        while not task.done():
            self.async_sleep(0.1)

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
        self.async_sleep(0.1)
        self.assertIsNotNone(self.peer.request)

    def test_METHOD_start__creates_subscriber_socket(self):
        self.peer.start()
        self.async_sleep(4)

        self.assertIsNotNone(self.peer.subscriber)

    def test_METHOD_start__sets_running_to_TRUE(self):
        self.peer.start()
        self.async_sleep(0.1)
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

    def test_METHOD_verify_peer__sets_verified_when_peer_exists(self):
        self.peer.setup_request()

        task = asyncio.ensure_future(self.peer.verify_peer())
        while not task.done():
            self.async_sleep(0.1)

        self.assertTrue(self.peer.is_verified)

    def test_METHOD_verify_peer__returns_when_peer_doesnt_exist(self):
        self.peer.set_ip(address='tcp://127.0.0.1:19001')
        self.peer.setup_request()

        task = asyncio.ensure_future(self.peer.verify_peer())
        while not task.done():
            self.async_sleep(0.1)

        self.assertFalse(self.peer.is_verified)

    def test_METHOD_verify_peer__calls_connected_callback_if_exists_and_passes_vk(self):
        self.peer.setup_request()
        self.peer.connected_callback = self.connected_callback

        task = asyncio.ensure_future(self.peer.verify_peer())
        while not task.done():
            self.async_sleep(0.1)

        self.assertEqual(self.peer.server_vk, self.connected_callback_called)

    def test_METHOD_verify_peer__starts_subscriber(self):
        self.peer.setup_request()

        task = asyncio.ensure_future(self.peer.verify_peer())
        while not task.done():
            self.async_sleep(0.1)

        self.async_sleep(2)
        self.assertIsNotNone(self.peer.subscriber)
        self.assertTrue(self.peer.subscriber.is_running)

    def test_METHOD_verify_peer__bubbles_AttributeError_if_socket_not_setup(self):
        with self.assertRaises(AttributeError) as error:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.peer.verify_peer())

        self.assertEqual("Request socket not setup.", str(error.exception))
        self.assertFalse(self.peer.is_verified)

    def test_METHOD_verify_peer_loop__verified_remains_FALSE_if_peer_unresponsive(self):
        self.peer.setup_request()
        self.peer.socket_ports['router'] = 1000

        task = asyncio.ensure_future(self.peer.verify_peer_loop())
        while not task.done():
            self.async_sleep(0.1)

        self.assertFalse(self.peer.is_verified)

    def test_METHOD_start_verify_peer_loop__creates_verified_peer_task(self):
        self.peer.setup_request()
        self.peer.running = True

        self.peer.start_verify_peer_loop()

        task = asyncio.ensure_future(self.peer.verify_peer_loop())

        while not task.done():
            self.async_sleep(0.1)

        self.assertIsNotNone(self.peer.verify_task)

    def test_METHOD_start_verify_peer_loop__returns_if_is_verifying_is_True(self):
        async def mock_verify_task():
            self.async_sleep(0)

        self.peer.setup_request()
        self.peer.running = True

        task = asyncio.ensure_future(mock_verify_task())

        self.peer.verify_task = task

        self.peer.start_verify_peer_loop()

        self.assertEqual(task, self.peer.verify_task)


    def test_METHOD_verify_peer_loop__sets_peer_is_verified(self):
        self.peer.setup_request()
        self.peer.running = True

        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.peer.verify_peer_loop())

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

    def test_METHOD_restart(self):
        self.peer.start()

        while not self.peer.is_connected:
            self.async_sleep(0.1)

        self.assertIsNotNone(self.peer.subscriber)

        task = asyncio.ensure_future(self.peer.restart())
        while not task.done():
            self.async_sleep(0.1)

        self.async_sleep(1)
        self.assertIsNotNone(self.peer.subscriber)

    def test_METHOD_update_ip(self):
        remote_peer = MockRouter(
            valid_peers=[self.local_wallet.curve_vk],
            wallet=self.remote_peer_wallet,
            port=19001
        )
        while not remote_peer.running:
            self.async_sleep(0.1)

        self.peer.start()

        while not self.peer.is_connected:
            self.async_sleep(0.1)

        new_ip = 'tcp://127.0.0.1:19001'

        self.assertIsNotNone(self.peer.subscriber)

        task = asyncio.ensure_future(self.peer.update_ip(new_ip=new_ip))

        while not task.done():
            self.async_sleep(0.1)

        self.async_sleep(1)

        while not self.peer.is_connected:
            self.async_sleep(0.1)

        self.assertIsNotNone(self.peer.subscriber)
        self.assertEqual(new_ip, self.peer.request_address)
        self.assertTrue(self.peer.is_connected)

        remote_peer.stop()
        remote_peer.join()

    def test_METHOD_test_connection__returns_True_if_peer_available(self):
        self.peer.start()

        while not self.peer.is_connected:
            self.async_sleep(0.1)

        task = asyncio.ensure_future(self.peer.test_connection())
        while not task.done():
            self.async_sleep(0.1)

        loop = asyncio.get_event_loop()

        res = loop.run_until_complete(asyncio.gather(task))

        self.assertTrue(res[0])
        self.assertTrue(self.peer.connected)

    def test_METHOD_test_connection__returns_False_if_peer_unavailable(self):
        self.peer.start()


        while not self.peer.is_connected:
            self.async_sleep(0.1)

        self.peer.set_ip(address='tcp://127.0.0.1:19001')

        task = asyncio.ensure_future(self.peer.test_connection())
        while not task.done():
            self.async_sleep(0.1)

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(asyncio.gather(task))

        self.assertFalse(res[0])
        self.assertFalse(self.peer.connected)
        self.assertTrue(self.peer.reconnecting)
