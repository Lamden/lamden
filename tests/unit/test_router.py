import unittest
import asyncio
import uvloop

from lamden.sockets.router import Router, EXCEPTION_NO_SOCKET, EXCEPTION_NO_ADDRESS_SET, EXCEPTION_IP_NOT_TYPE_STR, EXCEPTION_PORT_NOT_TYPE_INT
from lamden.crypto.wallet import Wallet

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

class TestRouter(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.router_wallet = Wallet()

    def setUp(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.wallet = self.__class__.router_wallet
        self.router = None
        self.all_peers = []

    def tearDown(self) -> None:
        if self.router:
            self.router.stop()
            del self.router

        loop = asyncio.get_event_loop()
        loop.stop()
        loop.close()

    def create_router(self):
        self.router = Router(
            router_wallet=self.router_wallet
        )

    def get_all_peers(self):
        return self.all_peers

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def test_can_create_instance(self):
        self.create_router()
        self.assertIsNotNone(self.router)

    def test_can_create_Router_instance(self):
        self.create_router()
        self.assertIsNotNone(self.router)
        self.assertIsInstance(self.router, Router)

    def test_PROPERTY_socket_is_bound__return_TRUE(self):
        self.create_router()
        self.router.create_socket()
        self.router.set_address(ip='127.0.0.1', port=19000)

        self.assertFalse(self.router.socket_is_bound)
        self.router.connect_socket()
        self.assertTrue(self.router.socket_is_bound)

    def test_PROPERTY_socket_is_bound__return_FALSE(self):
        self.create_router()
        self.router.create_socket()

        self.assertFalse(self.router.socket_is_bound)

    def test_PROPERTY_socket_is_closed__return_TRUE(self):
        self.create_router()
        self.router.create_socket()
        self.router.socket.close()

        self.assertTrue(self.router.socket_is_closed)

    def test_PROPERTY_socket_is_closed__return_FALSE(self):
        self.create_router()
        self.router.create_socket()

        self.assertFalse(self.router.socket_is_closed)

    def test_PROPERTY_curve_server_setup__return_TRUE(self):
        self.create_router()
        self.router.create_socket()
        self.router.setup_authentication_keys()

        self.assertTrue(self.router.curve_server_setup)

    def test_PROPERTY_curve_server_setup__return_FALSE(self):
        self.create_router()
        self.router.create_socket()

        self.assertFalse(self.router.curve_server_setup)

    def test_METHOD_create_context(self):
        self.create_router()

        self.assertIsNone(self.router.ctx)
        self.router.create_context()
        self.assertIsNotNone(self.router.ctx)

    def test_METHOD_create_socket__if_context_exists(self):
        self.create_router()
        self.router.create_context()
        self.router.create_socket()

        self.assertIsNotNone(self.router.socket)

    def test_METHOD_create_socket__if_context_does_not_exist(self):
        self.create_router()
        self.router.create_socket()

        self.assertIsNotNone(self.router.socket)

    def test_METHOD_connect_socket(self):
        self.create_router()
        self.router.create_socket()
        self.router.set_address(ip='127.0.0.1', port=19000)
        self.router.connect_socket()

        self.assertTrue(len(self.router.socket.LAST_ENDPOINT) > 0)

    def test_METHOD_connect_socket__raises_AttributeError_if_no_address_set(self):
        self.create_router()

        with self.assertRaises(AttributeError) as error:
            self.router.connect_socket()

        self.assertEqual(EXCEPTION_NO_ADDRESS_SET, str(error.exception))

    def test_METHOD_connect_socket__raises_AttributeError_if_socket_is_none(self):
        self.create_router()
        self.router.set_address(ip='127.0.0.1', port=19000)

        with self.assertRaises(AttributeError) as error:
            self.router.connect_socket()

        self.assertEqual(EXCEPTION_NO_SOCKET, str(error.exception))

    def test_METHOD_set_address__sets_default_values(self):
        self.create_router()
        self.router.address = 'testing'
        self.router.set_address()

        self.assertEqual('tcp://*:19080', self.router.address)

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

    def test_METHOD_create_poller(self):
        self.create_router()
        self.router.create_socket()
        self.router.create_poller()
        self.assertIsNotNone(self.router.poller)

    def test_METHOD_create_poller__raises_AttributeError_if_socket_is_not_created(self):
        self.create_router()
        with self.assertRaises(AttributeError) as error:
            self.router.create_poller()

        self.assertEqual(EXCEPTION_NO_SOCKET, str(error.exception))

    def test_METHOD_setup_authentication(self):
        self.create_router()
        self.router.create_socket()
        self.router.setup_authentication()

    def test_METHOD_setup_authentication_keys(self):
        self.create_router()
        self.router.create_socket()
        self.router.setup_authentication_keys()

        self.assertTrue(self.router.curve_server_setup)

    def test_METHOD_setup_authentication_keys__raises_AttributeError_if_socket_is_not_created(self):
        self.create_router()
        with self.assertRaises(AttributeError) as error:
            self.router.setup_authentication_keys()

        self.assertEqual(EXCEPTION_NO_SOCKET, str(error.exception))


