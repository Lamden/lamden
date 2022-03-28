import json
import asyncio
from lamden.crypto.wallet import Wallet
from tests.unit.helpers.mock_publisher import MockPublisher

import unittest
import zmq

from lamden.sockets.subscriber import Subscriber

class TestSubscriberSocket(unittest.TestCase):
    def setUp(self):
        self.ctx = zmq.Context()
        self.request_wallet = Wallet()
        self.peer_wallet = Wallet()

        self.publisher_address = 'tcp://127.0.0.1:19000'
        self.publisher = None

        self.subscriber = Subscriber(
            address=self.publisher_address,
            callback=self.get_message
        )

        self.data = None
        self.message_received = None
        self.topic_received = None

    def tearDown(self):
        if self.publisher:
            self.publisher.stop()
        if self.subscriber:
            self.subscriber.stop()
            self.subscriber.join()

    def start_publisher(self):
        self.publisher = MockPublisher()

    def get_message(self, data):
        self.data = data

        topic, message = self.data
        self.message_received = json.loads(message.decode('UTF-8'))
        self.topic_received = topic.decode('UTF-8')


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

    def test_can_create_instance__SUBSCRIBER(self):
        self.assertIsInstance(self.subscriber, Subscriber)

    def test_thread_can_start(self):
        try:
            self.subscriber.start()
        except Exception:
            self.fail("Stop should not throw exception")

        self.async_sleep(1)
        self.assertTrue(self.subscriber.running)

    def test_PROPERTY_socket_is_bound__return_TRUE(self):
        self.subscriber.create_socket()

        self.assertFalse(self.subscriber.socket_is_bound)
        self.subscriber.connect_socket()
        self.assertTrue(self.subscriber.socket_is_bound)

    def test_PROPERTY_socket_is_bound__return_FALSE(self):
        self.subscriber.create_socket()

        self.assertFalse(self.subscriber.socket_is_bound)

    def test_PROPERTY_is_running__return_TRUE(self):
        self.subscriber.running = True
        self.assertTrue(self.subscriber.is_running)

    def test_PROPERTY_is_running__return_False(self):
        self.assertFalse(self.subscriber.is_running)

    def test_PROPERTY_socket_is_closed__return_True_if_socket_is_NONE(self):
        self.assertIsNone(self.subscriber.socket)
        self.assertTrue(self.subscriber.socket_is_closed)

    def test_PROPERTY_socket_is_closed__return_True(self):
        self.subscriber.create_socket()
        self.subscriber.socket.close()
        self.assertTrue(self.subscriber.socket_is_closed)

    def test_PROPERTY_socket_is_closed__return_False(self):
        self.subscriber.create_socket()
        self.subscriber.connect_socket()
        self.assertFalse(self.subscriber.socket_is_closed)

    def test_METHOD_stop__raises_no_errors(self):
        self.subscriber.start()
        self.async_sleep(0.1)
        self.assertTrue(self.subscriber.is_running)

        try:
            self.subscriber.stop()
        except Exception:
            self.fail("Stop should not throw exception")

        self.async_sleep(0.1)
        self.assertFalse(self.subscriber.is_running)
        self.assertTrue(self.subscriber.socket_is_closed)

    def test_METHOD_create_socket(self):
        self.subscriber.create_socket()
        self.assertIsNotNone(self.subscriber.socket)

    def test_METHOD_connect_socket(self):
        self.subscriber.create_socket()
        self.subscriber.connect_socket()

        self.assertTrue(len(self.subscriber.socket.LAST_ENDPOINT) > 0)

    def test_METHOD_setup_event_loop__creates_loop_if_none_exist(self):
        self.assertIsNone(self.subscriber.loop)
        self.subscriber.setup_event_loop()
        self.assertIsNotNone(self.subscriber.loop)

    def test_METHOD_setup_event_loop__uses_existing_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.assertIsNone(self.subscriber.loop)
        self.subscriber.setup_event_loop()
        self.assertIsNotNone(self.subscriber.loop)
        self.assertEqual(loop, self.subscriber.loop)

    def test_METHOD_add_topic(self):
        self.subscriber.create_socket()
        self.subscriber.add_topic("test_2")
        self.assertListEqual(['', 'test_2'], self.subscriber.topics)

    def test_METHOD_add_topic__enforces_string(self):
        with self.assertRaises(TypeError):
            self.subscriber.add_topic(1)

        self.assertListEqual([''], self.subscriber.topics)

    def test_METHOD_subscribe_to_topics(self):
        self.subscriber.create_socket()
        self.subscriber.topics.append('testing')

        try:
            self.subscriber.subscribe_to_topics()
        except Exception:
            self.fail("Stop should not throw exception")


    def test_METHOD_subscribe_to_topics__error_if_no_socket(self):
        with self.assertRaises(AttributeError):
            self.subscriber.subscribe_to_topics()

    def test_METHOD_subscriber_thread__gets_message_and_topic(self):
        self.start_publisher()
        self.subscriber.start()

        self.async_sleep(0.06)

        self.assertTrue(self.subscriber.is_running)
        self.assertTrue(self.subscriber.socket_is_bound)
        self.assertFalse(self.subscriber.socket_is_closed)

        msg = "testing"
        topic = "testing"

        self.subscriber.add_topic(topic=topic)
        self.publisher.publish(topic=topic, msg=msg)
        self.async_sleep(0.5)

        self.assertEqual(msg, self.message_received)
        self.assertEqual(topic, self.topic_received)

    def test_METHOD_subscriber_thread__returns_list_of_bytes_len_2(self):
        self.start_publisher()
        self.subscriber.start()

        self.async_sleep(0.1)

        self.publisher.publish(topic='test', msg='test')

        self.async_sleep(0.5)

        self.assertIsInstance(self.data, list)
        self.assertEqual(2, len(self.data))
        for val in self.data:
            self.assertIsInstance(val, bytes)





