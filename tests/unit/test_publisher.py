import unittest
import zmq
import asyncio

from lamden.sockets.publisher import Publisher, EXCEPTION_NO_ADDRESS_INFO


class TestPublisherSocket(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pass

    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.publisher = Publisher()
        pass

    def tearDown(self) -> None:
        if self.publisher:
            self.publisher.stop()
            del self.publisher

    @classmethod
    def tearDownClass(cls) -> None:
        pass

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def test_can_create_instance(self):
        self.assertIsInstance(self.publisher, Publisher)

    def test_PROPERTY_has_address__return_TRUE_if_address_is_set(self):
        self.publisher.address = "testing"
        self.assertTrue(self.publisher.has_address)

    def test_PROPERTY_has_address__return_FALSE_if_address_is_NONE(self):
        self.assertFalse(self.publisher.has_address)

    def test_PROPERTY_is_running__return_TRUE_if_running_is_TRUE(self):
        self.publisher.running = True
        self.assertTrue(self.publisher.is_running)

    def test_PROPERTY_is_running__return_FALSE_if_running_is_FALSE(self):
        self.publisher.running = False
        self.assertFalse(self.publisher.is_running)

    def test_PROPERTY_socket_is_bound__return_FALSE_if_socket_is_NONE(self):
        self.assertFalse(self.publisher.socket_is_bound)

    def test_PROPERTY_socket_is_bound__return_FALSE_if_socket_exist_but_not_connected(self):
        self.publisher.create_socket()
        self.assertFalse(self.publisher.socket_is_bound)

    def test_PROPERTY_socket_is_bound__return_TRUE_is_socket_is_connected(self):
        self.publisher.set_address()
        self.publisher.create_socket()
        self.publisher.connect_socket()
        self.assertTrue(self.publisher.socket_is_bound)

    def test_METHOD_create_socket(self):
        self.publisher.create_socket()
        self.assertIsNotNone(self.publisher.socket)

    def test_METHOD_create_socket__returns_if_bound_socket_exists_already(self):
        self.publisher.set_address()
        self.publisher.create_socket()
        self.publisher.connect_socket()

        self.assertTrue(self.publisher.socket_is_bound)

        try:
            self.publisher.create_socket()
        except:
            self.fail("Calling create_socket the second time should do nothing if socket is bound.")

    def test_METHOD_connect_socket(self):
        self.publisher.set_address()
        self.publisher.create_socket()
        self.publisher.connect_socket()

        self.assertTrue(len(self.publisher.socket.LAST_ENDPOINT) > 0)

    def test_METHOD_connect_socket__raises_Attreibute_Error_if_address_is_None(self):
        self.publisher.create_socket()

        with self.assertRaises(AttributeError) as error:
            self.publisher.connect_socket()

        self.assertEqual(EXCEPTION_NO_ADDRESS_INFO, str(error.exception))

    def test_METHOD_connect_socket__returns_if_socket_already_bound(self):
        self.publisher.set_address()
        self.publisher.create_socket()
        self.publisher.connect_socket()

        self.assertTrue(self.publisher.socket_is_bound)

        try:
            self.publisher.connect_socket()
        except:
            self.fail("Calling connect_socket the second time should do nothing if socket is bound.")

    def test_METHOD_start__sets_running_to_TRUE(self):
        self.publisher.set_address()
        self.publisher.start()

        self.assertTrue(self.publisher.is_running)

    def test_METHOD_start__creates_a_bound_socket(self):
        self.publisher.set_address()
        self.publisher.start()

        self.assertTrue(self.publisher.socket_is_bound)

    def test_METHOD_start__returns_if_already_running_and_causes_no_error(self):
        self.publisher.set_address()
        self.publisher.start()

        try:
            self.publisher.start()
        except:
            self.fail("Calling start() once running should cause no errors.")


