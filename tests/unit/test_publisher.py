import json
import unittest
import zmq
import asyncio
import uvloop

from lamden.sockets.publisher import Publisher, EXCEPTION_NO_ADDRESS_INFO, EXCEPTION_MSG_NOT_DICT, EXCEPTION_MSG_BYTES_NOT_BYTES, EXCEPTION_TOPIC_BYTES_NOT_BYTES, EXCEPTION_TOPIC_STR_NOT_STRING
from tests.unit.helpers.mock_subscriber import MockSubscriber

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

class TestPublisherSocket(unittest.TestCase):
    def setUp(self):
        self.publisher = None
        self.subscriber = None

        self.data = None

    def tearDown(self) -> None:
        if self.publisher:
            self.publisher.stop()
            del self.publisher
        if self.subscriber:
            self.subscriber.stop()
            del self.subscriber

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def create_publisher(self):
        self.publisher = Publisher()

    def start_subscriber(self, multipart=True):
        self.subscriber = MockSubscriber(callback=self.message_callback, multipart=multipart)
        self.subscriber.start()
        self.async_sleep(1)

    def message_callback(self, data):
        self.data = data

    def test_can_create_instance(self):
        self.create_publisher()
        self.assertIsInstance(self.publisher, Publisher)

    def test_instance__uses_existing_async_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.create_publisher()

        self.assertEqual(loop, self.publisher.loop)

    def test_instance__create_event_loop_if_one_does_not_exist(self):
        self.create_publisher()

        loop = asyncio.get_event_loop()
        self.assertEqual(loop, self.publisher.loop)

    def test_PROPERTY_has_address__return_TRUE_if_address_is_set(self):
        self.create_publisher()
        self.publisher.address = "testing"
        self.assertTrue(self.publisher.has_address)

    def test_PROPERTY_has_address__return_FALSE_if_address_is_NONE(self):
        self.create_publisher()
        self.assertFalse(self.publisher.has_address)

    def test_PROPERTY_is_running__return_TRUE_if_running_is_TRUE(self):
        self.create_publisher()
        self.publisher.running = True
        self.assertTrue(self.publisher.is_running)

    def test_PROPERTY_is_running__return_FALSE_if_running_is_FALSE(self):
        self.create_publisher()
        self.publisher.running = False
        self.assertFalse(self.publisher.is_running)

    def test_PROPERTY_socket_is_bound__return_FALSE_if_socket_is_NONE(self):
        self.create_publisher()
        self.assertFalse(self.publisher.socket_is_bound)

    def test_PROPERTY_socket_is_bound__return_FALSE_if_socket_exist_but_not_connected(self):
        self.create_publisher()
        self.publisher.create_socket()
        self.assertFalse(self.publisher.socket_is_bound)

    def test_PROPERTY_socket_is_bound__return_TRUE_is_socket_is_connected(self):
        self.create_publisher()
        self.publisher.set_address(ip="127.0.0.1")
        self.publisher.create_socket()
        self.publisher.connect_socket()
        self.assertTrue(self.publisher.socket_is_bound)

    def test_PROPERTY_socket_is_closed__return_True_if_socket_is_NONE(self):
        self.create_publisher()
        self.assertIsNone(self.publisher.socket)
        self.assertTrue(self.publisher.socket_is_closed)

    def test_PROPERTY_socket_is_closed__return_True(self):
        self.create_publisher()
        self.publisher.create_socket()
        self.async_sleep(0.5)
        self.publisher.socket.close()
        self.assertTrue(self.publisher.socket_is_closed)

    def test_PROPERTY_socket_is_closed__return_False(self):
        self.create_publisher()
        self.publisher.create_socket()
        self.publisher.set_address(ip="127.0.0.1")
        self.publisher.connect_socket()
        self.assertFalse(self.publisher.socket_is_closed)

    def test_METHOD_create_socket(self):
        self.create_publisher()
        self.publisher.create_socket()
        self.assertIsNotNone(self.publisher.socket)

    def test_METHOD_create_socket__returns_if_bound_socket_exists_already(self):
        self.create_publisher()
        self.publisher.set_address(ip="127.0.0.1")
        self.publisher.create_socket()
        self.publisher.connect_socket()

        self.assertTrue(self.publisher.socket_is_bound)

        try:
            self.publisher.create_socket()
        except:
            self.fail("Calling create_socket the second time should do nothing if socket is bound.")

    def test_METHOD_connect_socket__socket_connects_to_specific_ip(self):
        self.create_publisher()
        self.publisher.set_address(ip="127.0.0.1")
        self.publisher.create_socket()
        self.publisher.connect_socket()

        self.assertTrue("127.0.0.1" in self.publisher.socket.LAST_ENDPOINT.decode('UTF-8'))

    def test_METHOD_connect_socket__binds_to_wildcard_if_no_ip_specified(self):
        self.create_publisher()
        self.publisher.set_address()
        self.publisher.create_socket()
        self.publisher.connect_socket()

        self.assertTrue("0.0.0.0" in self.publisher.socket.LAST_ENDPOINT.decode('UTF-8'))

    def test_METHOD_connect_socket__raises_Attreibute_Error_if_address_is_None(self):
        self.create_publisher()
        self.publisher.create_socket()

        with self.assertRaises(AttributeError) as error:
            self.publisher.connect_socket()

        self.assertEqual(EXCEPTION_NO_ADDRESS_INFO, str(error.exception))

    def test_METHOD_connect_socket__returns_if_socket_already_bound(self):
        self.create_publisher()
        self.publisher.set_address(ip="127.0.0.1")
        self.publisher.create_socket()
        self.publisher.connect_socket()

        self.assertTrue(self.publisher.socket_is_bound)

        try:
            self.publisher.connect_socket()
        except:
            self.fail("Calling connect_socket the second time should do nothing if socket is bound.")

    def test_METHOD_set_address__sets_default_values(self):
        self.create_publisher()
        self.publisher.address = 'testing'
        self.publisher.set_address()

        self.assertEqual('tcp://*:19080', self.publisher.address)

    def test_METHOD_set_address__sets_specified_value(self):
        self.create_publisher()
        self.publisher.address = 'testing'
        self.publisher.set_address(ip="127.0.0.1", port=1200)

        self.assertEqual('tcp://127.0.0.1:1200', self.publisher.address)

    def test_METHOD_set_address__port_not_int_raises_TypeError(self):
        self.create_publisher()
        with self.assertRaises(TypeError) as error:
            self.publisher.set_address(port='1200')

        self.assertEqual("Port must be type integer.", str(error.exception))

    def test_METHOD_set_address__ip_not_str_raises_TypeError(self):
        self.create_publisher()
        with self.assertRaises(TypeError) as error:
            self.publisher.set_address(ip=1200)

        self.assertEqual("Ip must be type string.", str(error.exception))

    def test_METHOD_start__sets_running_to_TRUE(self):
        self.create_publisher()
        self.publisher.set_address(ip="127.0.0.1")
        self.publisher.start()

        self.assertTrue(self.publisher.is_running)

    def test_METHOD_start__creates_a_bound_socket(self):
        self.create_publisher()
        self.publisher.set_address(ip="127.0.0.1")
        self.publisher.start()

        self.assertTrue(self.publisher.socket_is_bound)

    def test_METHOD_start__returns_if_already_running_and_causes_no_error(self):
        self.create_publisher()
        self.publisher.set_address(ip="127.0.0.1")
        self.publisher.start()

        try:
            self.publisher.start()
        except:
            self.fail("Calling start() once running should raise no errors.")

    def test_METHOD_stop__raises_no_errors(self):
        self.create_publisher()
        self.publisher.set_address(ip="127.0.0.1")
        self.publisher.start()
        self.async_sleep(0.5)

        try:
            self.publisher.stop()
        except:
            self.fail("Calling stop() should raise no errors.")

    def test_METHOD_stop__closes_socket(self):
        self.create_publisher()
        self.publisher.set_address(ip="127.0.0.1")
        self.publisher.start()
        self.async_sleep(0.5)

        self.publisher.stop()
        self.async_sleep(0.5)

        self.assertTrue(self.publisher.socket.closed)

    def test_METHOD_send_multipart_message__sends_a_multipart_message(self):
        self.create_publisher()
        self.publisher.set_address(ip="127.0.0.1")
        self.publisher.start()

        self.start_subscriber()

        topic = 'testing'
        msg_dict = {'testing': True}
        msg_bytes = json.dumps(msg_dict).encode('UTF-8')
        self.publisher.send_multipart_message(topic_bytes=topic.encode('UTF-8'), msg_bytes=msg_bytes)

        self.async_sleep(1)

        self.assertIsNotNone(self.data)
        self.assertEqual(topic, self.data[0].decode('UTF-8'))
        self.assertEqual(msg_dict, json.loads(self.data[1]))

    def test_METHOD_send_multipart_message__raises_TypeError_on_non_bytes_topic(self):
        self.create_publisher()
        topic = 'testing'
        msg_dict = {'testing': True}
        msg_bytes = json.dumps(msg_dict).encode('UTF-8')

        with self.assertRaises(TypeError) as error:
            self.publisher.send_multipart_message(topic_bytes=topic, msg_bytes=msg_bytes)

        self.assertEqual(EXCEPTION_TOPIC_BYTES_NOT_BYTES, str(error.exception))

    def test_METHOD_send_multipart_message__raises_TypeError_on_non_bytes_msg(self):
        self.create_publisher()
        topic = 'testing'
        msg_dict = {'testing': True}

        with self.assertRaises(TypeError) as error:
            self.publisher.send_multipart_message(topic_bytes=topic.encode('UTF-8'), msg_bytes=msg_dict)

        self.assertEqual(EXCEPTION_MSG_BYTES_NOT_BYTES, str(error.exception))


    def test_METHOD_publish__sends_a_multipart_message_str_topic_then_json_object(self):
        self.create_publisher()
        self.publisher.set_address(ip="127.0.0.1")
        self.publisher.start()

        self.start_subscriber()

        topic = 'testing'
        msg_dict = {'testing': True}
        self.publisher.publish(topic_str=topic, msg_dict=msg_dict)

        self.async_sleep(1)

        self.assertIsNotNone(self.data)
        self.assertEqual(topic, self.data[0].decode('UTF-8'))
        self.assertEqual(msg_dict, json.loads(self.data[1]))

    def test_METHOD_publish__raises_TypeError_on_non_dict_msg(self):
        self.create_publisher()
        self.publisher.running = True

        topic = 'testing'
        msg_dict = {'testing': True}
        msg_bytes = json.dumps(msg_dict).encode('UTF-8')

        with self.assertRaises(TypeError) as error:
            self.publisher.publish(topic_str=topic, msg_dict=msg_bytes)

        self.assertEqual(EXCEPTION_MSG_NOT_DICT, str(error.exception))

    def test_METHOD_publish__raises_TypeError_on_non_string_topic(self):
        self.create_publisher()
        self.publisher.running = True

        topic = 'testing'
        msg_dict = {'testing': True}

        with self.assertRaises(TypeError) as error:
            self.publisher.publish(topic_str=topic.encode('UTF-8'), msg_dict=msg_dict)

        self.assertEqual(EXCEPTION_TOPIC_STR_NOT_STRING, str(error.exception))

    def test_METHOD_publish__does_not_publish_if_not_running(self):
        self.create_publisher()
        self.assertFalse(self.publisher.is_running)

        self.start_subscriber()

        topic = 'testing'
        msg_dict = {'testing': True}

        try:
            self.publisher.publish(topic_str=topic, msg_dict=msg_dict)
        except Exception:
            self.fail("calling publish() while not running should not cause an error.")

        self.async_sleep(1)

        self.assertIsNone(self.data)

    def test_METHOD_announce_new_peer_connection__sends_ip_and_vk(self):
        self.create_publisher()
        self.publisher.set_address(ip="127.0.0.1")
        self.publisher.start()

        self.start_subscriber()

        vk = 'testing_vk'
        ip = 'testing_ip'

        self.publisher.announce_new_peer_connection(vk=vk, ip=ip)

        self.async_sleep(1)

        self.assertIsNotNone(self.data)
        self.assertEqual("new_peer_connection", self.data[0].decode('UTF-8'))

        return_message =  json.loads(self.data[1])
        self.assertEqual(vk, return_message.get('vk'))
        self.assertEqual(ip, return_message.get('ip'))



