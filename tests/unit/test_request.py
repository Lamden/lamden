import json
import asyncio

import zmq.asyncio

from lamden.crypto.wallet import Wallet
from tests.unit.helpers.mock_router import MockRouter
from tests.unit.helpers.mock_reply import MockReply
import unittest

from lamden.sockets.request import Request, ATTRIBUTE_ERROR_TO_ADDRESS_NOT_NONE


class TestRequestSocket(unittest.TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()

        self.local_wallet = Wallet()
        self.peer_wallet = Wallet()

        self.peer_address = 'tcp://127.0.0.1:19000'
        self.peer = None
        self.request = None

        self.reconnect_called = False
        self.ping_msg = json.dumps("ping")

    def tearDown(self):
        if self.peer:
            self.peer.stop()
            self.peer.join()
        if self.request:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.request.stop())

        self.ctx.destroy(linger=0)


    def start_secure_peer(self):
        self.peer = MockRouter(
            valid_peers=[self.local_wallet.curve_vk],
            wallet=self.peer_wallet
        )

    def start_peer(self):
        self.peer = MockReply()

    def create_secure_request(self):
        self.request = Request(
            server_curve_vk=self.peer_wallet.curve_vk,
            local_wallet=self.local_wallet,
            to_address=self.peer_address,
            ctx=self.ctx
        )

    def create_request(self):
        self.request = Request(to_address=self.peer_address, ctx=self.ctx)

    async def wrap_process_in_async(self, process, args={}):
        process(**args)

    def await_async_process(self, process, args={}):
        tasks = asyncio.gather(
            process(**args)
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
    '''
    def test_can_create_instance_MOCKROUTER(self):
        self.start_secure_peer()
        self.assertIsInstance(obj=self.peer, cls=MockRouter)
        self.peer.stop()
        self.async_sleep(1)
        self.peer.join()

    def test_can_create_instance_MOCKREPLY(self):
        self.start_peer()
        self.assertIsInstance(obj=self.peer, cls=MockReply)
        self.peer.stop()
        self.async_sleep(1)
        self.peer.join()
    '''

    def test_can_create_instance_REQUEST(self):
        self.create_request()
        self.assertIsInstance(obj=self.request, cls=Request)
        self.assertFalse(self.request.secure_socket)

    def test_can_create_instance_secure_REQUEST(self):
        self.create_secure_request()
        self.assertIsInstance(obj=self.request, cls=Request)
        self.assertTrue(self.request.secure_socket)

    def test_METHOD_send__get_successful_response(self):
        self.start_peer()
        self.create_request()
        self.request.start()

        res = self.await_async_process(process=self.request.send, args={
            'str_msg': self.ping_msg
        })

        res = res[0]

        self.assertTrue(res.success)
        self.assertIsNone(res.error)
        self.assertIsNotNone(res.response)

        self.assertEqual(self.ping_msg, res.response.decode('UTF-8'))

    def test_METHOD_send__secure_msg_get_successful_response(self):
        self.start_secure_peer()
        self.create_secure_request()
        self.request.start()

        res = self.await_async_process(process=self.request.send, args={
            'str_msg': self.ping_msg
        })

        res = res[0]

        self.assertTrue(res.success)
        self.assertIsNone(res.error)
        self.assertIsNotNone(res.response)

        self.assertEqual(self.ping_msg, res.response.decode('UTF-8'))

    def test_METHOD_send__msg_no_receiver(self):
        self.create_request()
        self.request.start()

        attempts = 3
        timeout = 500

        res = self.await_async_process(process=self.request.send, args={
            'str_msg': self.ping_msg,
            'attempts': attempts,
            'timeout': timeout
        })

        res = res[0]

        self.assertFalse(res.success)
        error = f"Request Socket Error: Failed to receive response after {attempts} attempts each waiting {timeout}ms"

        self.assertEquals(error, res.error)
        self.assertIsNone(res.response)


    def test_METHOD_send__secure_msg_no_receiver(self):
        self.create_secure_request()
        self.request.start()

        attempts = 3
        timeout = 500

        res = self.await_async_process(process=self.request.send, args={
            'str_msg': self.ping_msg,
            'attempts': attempts,
            'timeout': timeout
        })

        res = res[0]

        self.assertFalse(res.success)
        error = f"Request Socket Error: Failed to receive response after {attempts} attempts each waiting {timeout}ms"
        self.assertEquals(error, res.error)
        self.assertIsNone(res.response)

    def test_METHOD_send__reg_socket_to_secure_peer_expect_no_response(self):
        self.start_secure_peer()
        self.create_request()
        self.request.start()

        attempts = 3
        timeout = 500

        res = self.await_async_process(process=self.request.send, args={
            'str_msg': self.ping_msg,
            'attempts': attempts,
            'timeout': timeout
        })

        res = res[0]

        self.assertFalse(res.success)
        error = f"Request Socket Error: Failed to receive response after {attempts} attempts each waiting {timeout}ms"

        self.assertEquals(error, res.error)
        self.assertIsNone(res.response)

    def test_METHOD_send__secure_socket_to_reg_peer_expect_no_response(self):
        self.start_peer()
        self.create_secure_request()
        self.request.start()

        attempts = 3
        timeout = 500

        res = self.await_async_process(process=self.request.send, args={
            'str_msg': self.ping_msg,
            'attempts': attempts,
            'timeout': timeout
        })

        res = res[0]

        self.assertFalse(res.success)
        error = f"Request Socket Error: Failed to receive response after {attempts} attempts each waiting {timeout}ms"

        self.assertEquals(error, res.error)
        self.assertIsNone(res.response)

    def test_METHOD_stop__will_stop_if_socket_is_None(self):
        # Does not throw exceptions or hang
        self.create_request()

        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.request.stop())
        except Exception:
            self.fail("Request did not stop cleanly!")

    def test_METHOD_stop__will_stop_if_socket_exists(self):
        self.create_request()
        self.request.start()

        # Does not throw exceptions or hang
        self.request.create_socket()

        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.request.stop())
        except Exception:
            self.fail("Request did not stop cleanly!")

    def test_METHOD_create_socket(self):
        self.create_request()
        self.request.create_socket()
        self.assertIsNotNone(self.request.socket)

    def test_METHOD_create_socket__secure(self):
        self.create_secure_request()
        self.request.create_socket()
        self.assertIsNotNone(self.request.socket)

    def test_METHOD_setup_polling__socket_is_None(self):
        self.create_request()
        self.request.setup_polling()

        self.assertIsNotNone(self.request.pollin)

    def test_METHOD_setup_polling__secure_socket_is_None(self):
        self.create_secure_request()
        self.request.setup_polling()

        self.assertIsNotNone(self.request.pollin)

    def test_METHOD_setup_polling__socket_is_setup(self):
        self.create_request()
        self.request.create_socket()
        self.request.setup_polling()

        self.assertIsNotNone(self.request.pollin)

    def test_METHOD_setup_polling__secure_socket_is_setup(self):
        self.create_secure_request()
        self.request.create_socket()
        self.request.setup_secure_socket()
        self.request.setup_polling()

        self.assertIsNotNone(self.request.pollin)

    def test_METHOD_start__creates_socket_and_poller(self):
        self.create_request()
        self.request.start()

        self.assertIsNotNone(self.request.socket)
        self.assertIsNotNone(self.request.pollin)

    def test_METHOD_start__raises_ATTRIBUTE_error_if_address_not_setup(self):
        self.create_request()
        self.request.to_address = None

        with self.assertRaises(AttributeError) as err:
            self.request.start()

        self.assertEqual(ATTRIBUTE_ERROR_TO_ADDRESS_NOT_NONE, str(err.exception))


    def test_METHOD_message_waiting__messages_waiting_FALSE(self):
        self.create_request()
        self.request.create_socket()
        self.request.setup_polling()

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(self.request.message_waiting(poll_time=100))

        self.assertFalse(res)

    def test_METHOD_message_waiting__secure_socket_messages_waiting_FALSE(self):
        self.create_secure_request()
        self.request.create_socket()
        self.request.setup_secure_socket()
        self.request.setup_polling()

        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(self.request.message_waiting(poll_time=100))

        self.assertFalse(res)

    def test_METHOD_message_waiting__messages_waiting_TRUE(self):
        self.start_peer()

        self.create_request()
        self.request.start()

        self.request.send_string(str_msg=self.ping_msg)
        self.async_sleep(1)
        self.assertTrue(self.request.message_waiting(poll_time=100))

    def test_METHOD_message_waiting__secure_socket_messages_waiting_TRUE(self):
        self.start_secure_peer()

        self.create_request()
        self.request.start()

        self.request.send_string(str_msg=self.ping_msg)
        self.async_sleep(1)
        self.assertTrue(self.request.message_waiting(poll_time=100))

    def test_METHOD_send_string__no_socket_setup_raises_AttributeError(self):
        self.create_request()

        with self.assertRaises(AttributeError) as err:
            self.request.send_string(str_msg=self.ping_msg)

        self.assertEqual("Socket has not been created.", str(err.exception))

    def test_METHOD_send_string__no_secure_socket_setup_raises_AttributeError(self):
        self.create_secure_request()

        with self.assertRaises(AttributeError) as err:
            self.request.send_string(str_msg=self.ping_msg)

        self.assertEqual("Socket has not been created.", str(err.exception))

    def test_METHOD_send_string__socket_setup_not_bound_raises_AttributeError(self):
        self.create_request()
        socket = self.request.create_socket()

        with self.assertRaises(AttributeError) as err:
            self.request.send_string(str_msg=self.ping_msg)

        self.assertEqual("Socket is not bound to an address.", str(err.exception))

    def test_METHOD_send_string__secure_socket_setup_not_bound_raises_AttributeError(self):
        self.create_secure_request()
        self.request.create_socket()
        self.request.setup_secure_socket()

        with self.assertRaises(AttributeError) as err:
            self.request.send_string(str_msg=self.ping_msg)

        self.assertEqual("Socket is not bound to an address.", str(err.exception))

    def test_METHOD_send_string__peer_does_not_exists_no_erorrs(self):
        self.create_request()
        self.request.create_socket()
        self.request.connect_socket()
        self.request.send_string(str_msg=self.ping_msg)

    def test_METHOD_send_string__peer_exists_no_erorrs(self):
        self.start_peer()
        self.create_request()
        self.request.create_socket()
        self.request.connect_socket()
        self.request.send_string(str_msg=self.ping_msg)

    def test_METHOD_send_string__reg_socket_to_secure_peer_no_erorrs(self):
        self.start_secure_peer()
        self.create_request()
        self.request.create_socket()
        self.request.connect_socket()
        self.request.send_string(str_msg=self.ping_msg)

    def test_METHOD_send_string__secure_socket_to_reg_peer_no_erorrs(self):
        self.start_peer()
        self.create_secure_request()
        self.request.create_socket()
        self.request.setup_secure_socket()
        self.request.connect_socket()
        self.request.send_string(str_msg=self.ping_msg)

    def test_METHOD_send_string__enforces_message_is_string(self):
        self.create_request()
        self.request.create_socket()
        self.request.connect_socket()
        with self.assertRaises(TypeError):
            self.request.send_string(str_msg=self.ping_msg.encode('UTF-8'))

    def test_METHOD_socket_is_bound__ret_TRUE(self):
        self.create_request()
        self.request.create_socket()
        self.request.connect_socket()

        self.assertTrue(self.request.socket_is_bound())

    def test_METHOD_socket_is_bound__socket_is_None_ret_FALSE(self):
        self.create_request()

        self.assertFalse(self.request.socket_is_bound())

    def test_METHOD_socket_is_bound__socket_not_connected_ret_FALSE(self):
        self.create_request()
        self.request.create_socket()

        self.assertFalse(self.request.socket_is_bound())

    def test_PROPERTY_id__ret_VK(self):
        self.create_request()
        self.request.create_socket()
        self.request.connect_socket()

        self.assertEqual(self.request.local_wallet.verifying_key, self.request.id)

    def test_PROPERTY_secure_socket__ret_TRUE(self):
        self.create_secure_request()
        self.assertTrue(self.request.secure_socket)

    def test_PROPERTY_secure_socket__ret_FALSE(self):
        self.create_request()
        self.assertFalse(self.request.secure_socket)

    def test_PROPERTY_secure_socket__manual_setup_of_server_vk_ret_TRUE(self):
        self.create_request()
        self.assertFalse(self.request.secure_socket)

        wallet = Wallet()
        self.request.server_curve_vk = wallet.curve_vk
        self.assertTrue(self.request.secure_socket)

    def test_PROPERTY_is_running__return_TRUE(self):
        self.create_request()
        self.request.running = True
        self.assertTrue(self.request.is_running)

    def test_PROPERTY_is_running__return_False(self):
        self.create_request()
        self.request.running = False
        self.assertFalse(self.request.is_running)

    def test_METHOD_send__can_send_multiple_requests_to_router_and_get_responses_back(self):
        self.start_peer()
        self.create_request()
        self.request.start()

        task_list = list()
        for i in range(20):
            task = asyncio.ensure_future(self.request.send(str_msg="TEST", timeout=200, attempts=1))
            task_list.append(task)

        tasks = asyncio.gather(*task_list)

        loop = asyncio.get_event_loop()
        task_results = loop.run_until_complete(tasks)

        passed = all([result.response.decode('UTF-8') == "TEST" for result in task_results])
        self.assertTrue(passed)

    def test_METHOD_send__can_send_multiple_requests_sequentially(self):
        self.start_peer()
        self.create_request()
        self.request.start()

        task_list = list()
        for i in range(20):
            task = asyncio.ensure_future(self.request.send(str_msg=f"{i}", timeout=200, attempts=1))
            task_list.append(task)

        tasks = asyncio.gather(*task_list)

        loop = asyncio.get_event_loop()
        task_results = loop.run_until_complete(tasks)

        passed = all([int(result.response.decode('UTF-8')) == index for index, result in enumerate(task_results) ])
        self.assertTrue(passed)

    def test_METHOD_send__can_send_multiple_SECURE_requests_to_router_and_get_responses_back(self):
        self.start_secure_peer()
        self.create_secure_request()
        self.request.start()

        loop = asyncio.get_event_loop()
        task_list = list()

        for i in range(200):
            task = asyncio.ensure_future(self.request.send(str_msg="TEST", timeout=20000, attempts=1))
            task_list.append(task)
            loop.run_until_complete(task)

        tasks = asyncio.gather(*task_list)

        task_results = loop.run_until_complete(tasks)

        passed = all([result.response.decode('UTF-8') == "TEST" for result in task_results])
        self.assertTrue(passed)

    def test_METHOD_send__can_send_multiple_SECURE_requests_sequentially(self):
        self.start_secure_peer()
        self.create_secure_request()
        self.request.start()

        task_list = list()
        for i in range(200):
            task = asyncio.ensure_future(self.request.send(str_msg=f"{i}", timeout=200, attempts=1))
            task_list.append(task)

        tasks = asyncio.gather(*task_list)

        loop = asyncio.get_event_loop()
        task_results = loop.run_until_complete(tasks)

        passed = all([int(result.response.decode('UTF-8')) == index for index, result in enumerate(task_results) ])
        self.assertTrue(passed)