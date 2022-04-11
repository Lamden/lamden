import unittest
import asyncio
import time
import json

from lamden.sockets.router import Router, EXCEPTION_PORT_NOT_TYPE_INT, EXCEPTION_IP_NOT_TYPE_STR, EXCEPTION_NO_SOCKET, EXCEPTION_NO_ADDRESS_SET, EXCEPTION_MSG_NOT_STRING, EXCEPTION_TO_VK_NOT_STRING
from lamden.crypto.wallet import Wallet

from tests.unit.helpers.mock_request import MockRequest
from tests.unit.helpers.mock_reply import MockReply

import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

class TestRouter(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.router_wallet = Wallet()
        cls.request_wallet = Wallet()

    def setUp(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.wallet = self.__class__.router_wallet
        self.request_wallet = self.__class__.request_wallet
        self.router = None
        self.request = None

        self.callback_data = None

        self.all_peers = list([])

    def tearDown(self) -> None:
        if self.router:
            self.router.stop()
            del self.router
        if self.request:
            self.request.stop()
            del self.request

        loop = asyncio.get_event_loop()
        loop.stop()
        loop.close()

    def get_all_peers(self):
        return self.all_peers

    def get_data(self, ident_vk_string, msg=None):
        self.callback_data = (ident_vk_string, msg)

    def create_router(self):
        self.router = Router(
            wallet=self.router_wallet,
            callback=self.get_data
        )

    def create_secure_router(self):
        self.router = Router(
            wallet=self.router_wallet,
            callback=self.get_data
        )
        self.router.setup_socket()
        self.router.setup_auth()
        self.router.register_poller()
        self.router.setup_auth_keys()

    def start_router(self):
        self.create_router()
        self.router.run_open_server()
        while not self.router.running:
            self.async_sleep(0.1)

    def start_secure_router(self):
        self.create_router()
        self.router.run_curve_server()
        self.router.cred_provider.add_key(vk=self.request_wallet.verifying_key)
        while not self.router.running:
            self.async_sleep(0.1)

    def create_request(self):
        self.request = MockRequest(
            local_wallet=self.request_wallet,
        )

    def create_secure_request(self):
        self.request = MockRequest(
            local_wallet=self.request_wallet,
            server_curve_vk=self.router_wallet.curve_vk
        )

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def test_can_create_instance(self):
        self.create_router()
        self.assertIsNotNone(self.router)

    def test_PROPERTY_socket_is_bound__return_TRUE(self):
        self.create_router()
        self.router.setup_socket()
        self.router.set_address(ip='*', port=19000)

        self.assertFalse(self.router.socket_is_bound)
        self.router.connect_socket()
        self.assertTrue(self.router.socket_is_bound)

    def test_PROPERTY_socket_is_bound__return_FALSE(self):
        self.create_router()
        self.router.setup_socket()

        self.assertFalse(self.router.socket_is_bound)

    def test_PROPERTY_auth_is_stopped__return_TRUE_if_auth_STOP_method_called(self):
        self.start_secure_router()
        self.async_sleep(0.1)
        self.router.auth.stop()
        self.async_sleep(0.1)
        self.assertTrue(self.router.auth_is_stopped)

    def test_PROPERTY_auth_is_stopped__return_TRUE_if_auth_is_None(self):
        self.start_router()
        self.assertTrue(self.router.auth_is_stopped)

    def test_PROPERTY_auth_is_stopped__return_FALSE_if_auth_is_started(self):
        self.start_secure_router()
        self.async_sleep(0.1)
        self.assertFalse(self.router.auth_is_stopped)

    def test_PROPERTY_auth_is_stopped__return_FALSE(self):
        self.create_router()
        self.router.setup_socket()

        self.assertFalse(self.router.socket_is_bound)

    def test_PROPERTY_socket_is_closed__return_TRUE(self):
        self.create_router()
        self.router.setup_socket()
        self.router.socket.close()

        self.assertTrue(self.router.socket_is_closed)

    def test_PROPERTY_socket_is_closed__return_FALSE(self):
        self.create_router()
        self.router.setup_socket()

        self.assertFalse(self.router.socket_is_closed)

    def test_PROPERTY_is_checking__return_TRUE_if_task_is_not_done(self):
        self.start_router()
        self.async_sleep(0.1)

        self.assertFalse(self.router.task_check_for_messages.done())
        self.assertTrue(self.router.is_checking)

    def test_PROPERTY_is_checking__return_FALSE_if_task_is_None(self):
        self.create_router()

        self.assertIsNone(self.router.task_check_for_messages)
        self.assertFalse(self.router.is_checking)

    def test_PROPERTY_is_checking__return_FALSE_if_task_is_done(self):
        self.start_router()
        self.router.running = False
        self.async_sleep(1)

        self.assertTrue(self.router.task_check_for_messages.done())
        self.assertFalse(self.router.is_checking)

    def test_PROPERTY_curve_server_setup__return_TRUE(self):
        self.create_router()
        self.router.setup_socket()
        self.router.setup_auth_keys()

        self.assertTrue(self.router.curve_server_setup)

    def test_PROPERTY_curve_server_setup__return_FALSE(self):
        self.create_router()
        self.router.setup_socket()

        self.assertFalse(self.router.curve_server_setup)

    def test_PROPERTY_curve_server_setup__return_FALSE_is_AttributeError(self):
        self.create_router()
        self.assertFalse(self.router.curve_server_setup)

    def test_METHOD_connect_socket(self):
        self.create_router()
        self.router.setup_socket()
        self.router.set_address()
        self.router.connect_socket()

        self.assertTrue(len(self.router.socket.LAST_ENDPOINT) > 0)

    def test_METHOD_connect_socket__raises_AttributeError_if_no_address_set(self):
        self.create_router()
        self.router.address = None

        with self.assertRaises(AttributeError) as error:
            self.router.connect_socket()

        self.assertEqual(EXCEPTION_NO_ADDRESS_SET, str(error.exception))

    def test_METHOD_connect_socket__raises_AttributeError_if_socket_is_none(self):
        self.create_router()
        self.router.set_address(ip='*', port=19000)

        with self.assertRaises(AttributeError) as error:
            self.router.connect_socket()

        self.assertEqual(EXCEPTION_NO_SOCKET, str(error.exception))

    def test_METHOD_register_poller(self):
        self.create_router()
        self.router.setup_socket()

        self.assertEqual([], self.router.poller.sockets)
        self.router.register_poller()
        self.assertEqual([(self.router.socket,1)], self.router.poller.sockets)

    def test_METHOD_register_poller__raises_AttributeError_if_socket_not_setup(self):
        self.create_router()

        with self.assertRaises(AttributeError) as error:
            self.router.register_poller()

        self.assertEqual(EXCEPTION_NO_SOCKET, str(error.exception))

    def test_METHOD_set_address__sets_default_values(self):
        self.create_router()
        self.router.address = 'testing'
        self.router.set_address()

        self.assertEqual('tcp://*:19000', self.router.address)

    def test_METHOD_set_address__sets_specified_value(self):
        self.create_router()
        self.router.address = 'testing'
        self.router.set_address(ip="127.0.0.1", port=1200)

        self.assertEqual('tcp://127.0.0.1:1200', self.router.address)

    def test_METHOD_set_address__port_not_int_raises_TypeError(self):
        self.create_router()
        with self.assertRaises(TypeError) as error:
            self.router.set_address(port='1200')

        self.assertEqual(EXCEPTION_PORT_NOT_TYPE_INT, str(error.exception))

    def test_METHOD_set_address__ip_not_str_raises_TypeError(self):
        self.create_router()
        with self.assertRaises(TypeError) as error:
            self.router.set_address(ip=1200)

        self.assertEqual(EXCEPTION_IP_NOT_TYPE_STR, str(error.exception))

    def test_METHOD_run_secure_server__can_start_router(self):
        try:
            self.start_secure_router()
        except:
            self.fail("Calling start method should not raise errors.")

        self.assertTrue(self.router.running)
        self.assertTrue(self.router.curve_server_setup)

    def test_METHOD_stop__router_can_stop_if_NOT_started(self):
        self.create_router()

        try:
            self.router.stop()
        except:
            self.fail("Calling stop method should not raise errors.")

        self.assertTrue(self.router.socket_is_closed)
        self.assertTrue(self.router.auth_is_stopped)
        self.assertFalse(self.router.is_checking)
        self.assertFalse(self.router.is_running)


    def test_METHOD_stop__secure_router_can_stop_if_started(self):
        self.start_secure_router()

        try:
            self.router.stop()
        except:
            self.fail("Calling stop method should not raise errors.")

        self.assertTrue(self.router.socket_is_closed)
        self.assertTrue(self.router.auth_is_stopped)
        self.assertFalse(self.router.is_checking)
        self.assertFalse(self.router.is_running)

    def test_METHOD_stop__unsecure_router_can_stop_if_started(self):
        self.start_router()

        try:
            self.router.stop()
        except:
            self.fail("Calling stop method should not raise errors.")

        self.assertTrue(self.router.socket_is_closed)
        self.assertTrue(self.router.auth_is_stopped)
        self.assertFalse(self.router.is_checking)
        self.assertFalse(self.router.is_running)


    def test_METHOD_check_for_messages__secure_server_can_decode_ident_and_pass_to_callback(self):
        self.create_secure_request()
        self.start_secure_router()


        to_address = 'tcp://127.0.0.1:19000'
        msg_str = "Testing"
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.request.send(to_address=to_address, msg_str=msg_str))

        self.async_sleep(1)

        self.assertIsNotNone(self.callback_data)

        ident_vk_string, msg = self.callback_data

        self.assertIsInstance(ident_vk_string, str)
        self.assertEqual(self.request_wallet.verifying_key, ident_vk_string)

    def test_METHOD_check_for_messages__unsecured_server_passes_NONE_for_ident_to_callback(self):
        self.create_request()
        self.start_router()


        to_address = 'tcp://127.0.0.1:19000'
        msg_str = "Testing"
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.request.send(to_address=to_address, msg_str=msg_str))

        self.async_sleep(1)

        self.assertIsNotNone(self.callback_data)

        ident_vk_string, msg = self.callback_data

        self.assertIsNone(ident_vk_string)

    def test_METHOD_check_for_messages__unsecured_server_passes_msg_as_bytes_to_callback(self):
        self.create_request()
        self.start_router()

        to_address = 'tcp://127.0.0.1:19000'
        msg_str = "Testing"
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.request.send(to_address=to_address, msg_str=msg_str))

        self.async_sleep(1)

        self.assertIsNotNone(self.callback_data)

        ident_vk_string, msg = self.callback_data

        self.assertIsInstance(msg, bytes)
        self.assertEqual(msg_str, msg.decode('UTF-8'))

    def test_METHOD_check_for_messages__secure_server_passes_msg_as_bytes_to_callback(self):
        self.create_secure_request()
        self.start_secure_router()


        to_address = 'tcp://127.0.0.1:19000'
        msg_str = "Testing"
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.request.send(to_address=to_address, msg_str=msg_str))

        self.async_sleep(1)

        self.assertIsNotNone(self.callback_data)

        ident_vk_string, msg = self.callback_data

        self.assertIsInstance(msg, bytes)
        self.assertEqual(msg_str, msg.decode('UTF-8'))


    def test_METHOD_check_for_messages__secure_server_ignores_unsecure_requests(self):
        self.create_request()
        self.start_secure_router()

        to_address = 'tcp://127.0.0.1:19000'
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.request.send(to_address=to_address, msg_str="Testing"))

        self.async_sleep(1)

        self.assertIsNone(self.callback_data)

    def test_METHOD_check_for_messages__secure_server_ignores_secure_request_if_no_key(self):
        self.create_secure_request()
        self.start_secure_router()
        self.router.cred_provider.remove_key(self.request_wallet.verifying_key)

        to_address = 'tcp://127.0.0.1:19000'
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.request.send(to_address=to_address, msg_str="Testing"))

        self.async_sleep(1)

        self.assertIsNone(self.callback_data)

    def test_METHOD_check_for_messages__unsecure_server_can_return_data_to_callback(self):
        self.create_request()
        self.request.server_curve_vk = None

        self.start_router()

        to_address = 'tcp://127.0.0.1:19000'
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.request.send(to_address=to_address, msg_str="Testing"))

        self.async_sleep(1)

        self.assertIsNotNone(self.callback_data)

    def test_METHOD_wait_for_socket_to_close__returns_when_socket_is_closed(self):
        self.create_router()
        self.router.setup_socket()
        self.router.connect_socket()

        self.assertTrue(self.router.socket_is_bound)

        task = asyncio.ensure_future(self.router.wait_for_socket_to_close())
        self.async_sleep(0.1)

        self.assertFalse(task.done())
        self.router.socket.close()
        self.async_sleep(0.1)

        self.assertTrue(task.done())

    def test_METHOD_stop_checking_for_messages__returns_when_stopped_checking(self):
        self.start_router()
        self.async_sleep(0.1)

        self.assertTrue(self.router.is_checking)

        task = asyncio.ensure_future(self.router.stop_checking_for_messages())
        self.async_sleep(1)

        self.assertTrue(task.done())
        self.assertFalse(self.router.is_checking)

    def test_METHOD_stop_auth__returns_when_auth_is_stopped(self):
        self.create_router()
        self.router.setup_socket()
        self.router.setup_auth()

        self.async_sleep(0.1)

        self.assertFalse(self.router.auth_is_stopped)

        task = asyncio.ensure_future(self.router.stop_auth())
        self.async_sleep(1)

        self.assertTrue(task.done())
        self.assertTrue(self.router.auth_is_stopped)

    def test_METHOD_stop_auth__returns_if_auth_not_started(self):
        self.create_router()
        self.router.setup_socket()

        self.assertTrue(self.router.auth_is_stopped)

        task = asyncio.ensure_future(self.router.stop_auth())
        self.async_sleep(0.5)

        self.assertTrue(task.done())
        self.assertTrue(self.router.auth_is_stopped)

    def test_METHOD_close_socket(self):
        self.create_router()
        self.router.setup_socket()
        self.router.connect_socket()
        self.async_sleep(0.1)

        self.assertFalse(self.router.socket_is_closed)
        self.assertTrue(self.router.socket_is_bound)
        self.router.close_socket()
        self.assertTrue(self.router.socket_is_closed)
        self.assertFalse(self.router.socket_is_bound)

    def test_METHOD_has_messages__unsecured_messages_return_TRUE(self):
        self.create_router()
        self.router.setup_socket()
        self.router.register_poller()
        self.router.connect_socket()
        self.async_sleep(1)

        self.create_request()

        to_address = 'tcp://127.0.0.1:19000'
        loop = asyncio.get_event_loop()

        event = False
        while not event:
            asyncio.ensure_future(self.request.send(to_address=to_address, msg_str="Testing"))
            event = loop.run_until_complete(self.router.has_message(timeout_ms=500))

        self.assertTrue(event == 1)

    def test_METHOD_has_messages__secured_messages_return_TRUE(self):
        self.create_router()
        self.router.setup_socket()
        self.router.setup_auth()
        self.router.cred_provider.add_key(vk=self.request_wallet.verifying_key)
        self.router.register_poller()
        self.router.setup_auth_keys()
        self.router.connect_socket()

        self.async_sleep(1)

        self.create_secure_request()

        to_address = 'tcp://127.0.0.1:19000'
        loop = asyncio.get_event_loop()

        event = False
        while not event:
            asyncio.ensure_future(self.request.send(to_address=to_address, msg_str="Testing"))
            event = loop.run_until_complete(self.router.has_message(timeout_ms=500))

        self.assertTrue(event == 1)

    def test_METHOD_has_messages__no_messages_return_FALSE_after_timout(self):
        self.create_router()
        self.router.setup_socket()
        self.router.setup_auth()
        self.router.register_poller()
        self.router.setup_auth_keys()
        self.router.connect_socket()

        self.async_sleep(1)

        start_time = time.time()
        timeout_ms = 1000
        timeout_sec = timeout_ms / 1000
        loop = asyncio.get_event_loop()
        event = loop.run_until_complete(self.router.has_message(timeout_ms=timeout_ms))
        end_time = time.time()
        elapsed_time = end_time - start_time

        self.assertTrue(elapsed_time > timeout_sec)
        self.assertTrue(event == 0)

    def test_METHOD_send_string(self):
        self.start_secure_router()
        self.create_secure_request()
        self.async_sleep(1)

        loop = asyncio.get_event_loop()

        to_address = 'tcp://127.0.0.1:19000'
        task = asyncio.ensure_future(self.request.send(to_address=to_address, msg_str="Testing", timeout_ms=1000))

        while self.callback_data is None:
            loop.run_until_complete(asyncio.sleep(0.1))

        msg_str = "Test_Test"
        self.router.send_msg(to_vk=self.request_wallet.verifying_key, msg_str=msg_str)

        while not task.done():
            self.async_sleep(0.1)

        result = loop.run_until_complete(task)

        self.assertTrue(result.success)
        self.assertEqual(msg_str.encode('UTF-8'), result.response)

    def test_METHOD_send_string__raise_AttributeError_if_to_vk_not_type_str(self):
        self.create_secure_router()

        with self.assertRaises(AttributeError) as error:
            self.router.send_msg(to_vk=self.request_wallet.curve_vk, msg_str="Test_Test")

        self.assertEqual(EXCEPTION_TO_VK_NOT_STRING, str(error.exception))

    def test_METHOD_send_string__raise_AttributeError_if_msg_str_not_type_string(self):
        self.create_secure_router()

        with self.assertRaises(AttributeError) as error:
            self.router.send_msg(to_vk=self.request_wallet.verifying_key, msg_str={"test": True})

        self.assertEqual(EXCEPTION_MSG_NOT_STRING, str(error.exception))

    def test_METHOD_send_string__raise_AttributeError_if_socket_is_None(self):
        self.create_router()

        with self.assertRaises(AttributeError) as error:
            self.router.send_msg(to_vk=self.request_wallet.verifying_key, msg_str="Test Test")

        self.assertEqual(EXCEPTION_NO_SOCKET, str(error.exception))