import json
import asyncio
import uvloop
import zmq

from lamden.crypto.wallet import Wallet
from tests.unit.helpers.mock_publisher import MockPublisher

import unittest
import time

from lamden.sockets.subscriber import Subscriber, EXCEPTION_TOPIC_NOT_STRING, EXCEPTION_NO_SOCKET

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

class TestSubscriberSocket(unittest.TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.request_wallet = Wallet()
        self.peer_wallet = Wallet()

        self.publisher_address = 'tcp://127.0.0.1:19080'
        self.publisher = None

        self.subscriber = Subscriber(
            address=self.publisher_address,
            callback=self.get_message,
            ctx=self.ctx
        )

        self.data = None
        self.message_received = None
        self.topic_received = None

    def tearDown(self):
        if self.publisher:
            self.publisher.stop()
            del self.publisher
        if self.subscriber:
            task = asyncio.ensure_future(self.subscriber.stop())
            while not task.done():
                self.async_sleep(0.1)
            del self.subscriber

        self.ctx.destroy(linger=0)

        loop = asyncio.get_event_loop()
        loop.stop()
        loop.close()

    def start_publisher(self):
        self.publisher = MockPublisher()
        self.await_async_process(self.wait_for_publisher_started)
        self.async_sleep(1)

    def start_subscriber(self):
        #self.start_publisher()
        self.subscriber.start()
        #self.await_async_process(self.wait_for_subscriber_started)
        self.async_sleep(1)

    async def get_message(self, data):
        self.data = data
        try:
            topic, message = self.data
            self.message_received = json.loads(message)
            self.topic_received = topic.decode('UTF-8')
        except Exception:
            pass

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

    async def wait_for_publisher_started(self):
        while not self.publisher.running:
            await asyncio.sleep(0.1)

    async def wait_for_subscriber_started(self):
        while not self.subscriber.running:
            await asyncio.sleep(0.1)

    async def wait_for_data(self):
        time_out = 500
        start = time.time()
        while not self.data:
            if time.time() - start > time_out:
                self.fail('Timed out waiting for data from subscriber.')
            await asyncio.sleep(0.5)

    def test_can_create_instance__SUBSCRIBER(self):
        self.assertIsInstance(self.subscriber, Subscriber)

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
        self.subscriber.connect_socket()
        self.assertFalse(self.subscriber.socket_is_closed)

    def test_PROPERTY_socket_is_closed__return_True(self):
        self.start_subscriber()
        self.assertTrue(self.subscriber.is_checking_for_messages)

    def test_PROPERTY_socket_is_closed__return_False_if_check_for_messages_task_is_None(self):
        self.assertFalse(self.subscriber.is_checking_for_messages)

    def test_PROPERTY_socket_is_closed__return_False_if_check_for_messages_task_is_Done(self):
        self.start_subscriber()

        task = asyncio.ensure_future(self.subscriber.stop())
        while not task.done():
            self.async_sleep(0.1)

        self.assertFalse(self.subscriber.is_checking_for_messages)

    def test_METHOD_stop__raises_no_errors(self):
        self.start_subscriber()
        self.async_sleep(0.1)
        self.assertTrue(self.subscriber.is_running)

        try:
            task = asyncio.ensure_future(self.subscriber.stop())
            while not task.done():
                self.async_sleep(0.1)
        except Exception:
            self.fail("Stop should not throw exception")

        self.async_sleep(1)
        self.assertFalse(self.subscriber.is_running)
        self.assertTrue(self.subscriber.socket_is_closed)

    def test_METHOD_stop__returns_if_no_socket(self):
        try:
            task = asyncio.ensure_future(self.subscriber.stop())
            while not task.done():
                self.async_sleep(0.1)
        except Exception:
            self.fail("Stop should not throw exception")

        self.async_sleep(1)
        self.assertFalse(self.subscriber.is_running)
        self.assertTrue(self.subscriber.socket_is_closed)

    def test_METHOD_stopping__loops_till_socket_is_closed(self):
        self.start_subscriber()

        self.assertFalse(self.subscriber.socket_is_closed)

        task = asyncio.ensure_future(self.subscriber.stopping())
        self.async_sleep(1)
        self.subscriber.socket.close()

        while not task.done():
            self.async_sleep(1)

        self.assertFalse(self.subscriber.socket_is_bound)

    def test_METHOD_create_socket(self):
        self.subscriber.create_socket()
        self.assertIsNotNone(self.subscriber.socket)

    def test_METHOD_connect_socket(self):
        self.subscriber.connect_socket()

        self.assertTrue(len(self.subscriber.socket.LAST_ENDPOINT) > 0)

    def test_METHOD_connect_socket__creates_socket_if_socket_is_None(self):
        self.assertIsNone(self.subscriber.socket)
        self.subscriber.connect_socket()

        self.assertIsNotNone(self.subscriber.socket)

    def test_METHOD_setup_event_loop__creates_loop_if_none_exist(self):
        loop = asyncio.get_event_loop()
        loop.stop()
        loop.close()

        self.assertIsNone(self.subscriber.loop)
        self.subscriber.setup_event_loop()
        self.assertIsNotNone(self.subscriber.loop)

    def test_METHOD_setup_event_loop__uses_existing_loop(self):
        loop = asyncio.get_event_loop()
        loop.stop()
        loop.close()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self.assertIsNone(self.subscriber.loop)
        self.subscriber.setup_event_loop()
        self.assertIsNotNone(self.subscriber.loop)
        self.assertEqual(loop, self.subscriber.loop)

    def test_METHOD_add_topic(self):
        self.subscriber.create_socket()
        self.subscriber.add_topic("test_1")
        self.subscriber.add_topic("test_2")
        self.assertListEqual(['test_1', 'test_2'], self.subscriber.topics)

    def test_METHOD_add_topic__enforces_string(self):
        with self.assertRaises(TypeError):
            self.subscriber.add_topic(1)

        self.assertListEqual([], self.subscriber.topics)

    def test_METHOD_subscribe_to_topics(self):
        self.subscriber.create_socket()
        self.subscriber.topics.append('testing')

        try:
            self.subscriber.subscribe_to_topics()
        except Exception:
            self.fail("Stop should not throw exception")

    def test_METHOD_subscribe_to_topics__raise_TypeError_if_no_socket(self):
        with self.assertRaises(AttributeError) as error:
            self.subscriber.subscribe_to_topics()

        self.assertEqual(EXCEPTION_NO_SOCKET, str(error.exception))

    def test_METHOD_subscribe_to_topics__raise_AttributeError_if_no_socket(self):
        self.subscriber.create_socket()
        self.subscriber.topics = ["testing", 2]

        with self.assertRaises(TypeError) as error:
            self.subscriber.subscribe_to_topics()

        self.assertEqual(EXCEPTION_TOPIC_NOT_STRING, str(error.exception))

    def test_METHOD_check_for_messages__gets_message_for_topic(self):
        self.start_publisher()
        self.async_sleep(1)

        msg_dict = {"testing": True}
        topic_str = "testing"

        self.subscriber.topics = [topic_str]
        self.start_subscriber()

        self.assertTrue(self.publisher.running)
        self.assertTrue(self.subscriber.running)

        self.assertTrue(self.subscriber.socket_is_bound)
        self.assertFalse(self.subscriber.socket_is_closed)

        self.async_sleep(1)
        self.publisher.publish_message_multipart(topic_str=topic_str, msg_dict=msg_dict)
        self.async_sleep(1)

        task = asyncio.ensure_future(self.subscriber.stop())
        while not task.done():
            self.async_sleep(0.1)

        self.publisher.stop()
        self.async_sleep(1)

        self.assertEqual(msg_dict, self.message_received)
        self.assertEqual(topic_str, self.topic_received)

    def test_METHOD_add_topic__gets_message_after_adding_topic(self):
        self.start_publisher()
        self.async_sleep(1)

        msg_dict = {"testing": True}
        topic_str = "testing"

        self.start_subscriber()
        self.subscriber.add_topic(topic_str)

        self.assertTrue(self.publisher.running)
        self.assertTrue(self.subscriber.running)

        self.assertTrue(self.subscriber.socket_is_bound)
        self.assertFalse(self.subscriber.socket_is_closed)

        self.async_sleep(1)
        self.publisher.publish_message_multipart(topic_str=topic_str, msg_dict=msg_dict)
        self.async_sleep(1)

        task = asyncio.ensure_future(self.subscriber.stop())
        while not task.done():
            self.async_sleep(0.1)

        self.publisher.stop()
        self.async_sleep(1)

        self.assertEqual(msg_dict, self.message_received)
        self.assertEqual(topic_str, self.topic_received)


    def test_METHOD_message_waiting__no_poll_event_if_no_topics_subscribed(self):
        self.start_publisher()
        self.async_sleep(1)

        msg_dict = {"testing": True}
        topic_str = "testing"

        self.start_subscriber()

        self.assertTrue(self.publisher.running)
        self.assertTrue(self.subscriber.running)

        self.assertTrue(self.subscriber.socket_is_bound)
        self.assertFalse(self.subscriber.socket_is_closed)

        self.async_sleep(1)
        self.publisher.publish_message_multipart(topic_str=topic_str, msg_dict=msg_dict)
        self.async_sleep(1)

        task = asyncio.ensure_future(self.subscriber.stop())
        while not task.done():
            self.async_sleep(0.1)

        self.publisher.stop()
        self.async_sleep(1)

        self.assertIsNone(self.data)

    def test_METHOD_messages_waiting(self):
        self.start_publisher()
        self.subscriber.connect_socket()
        self.subscriber.add_topic("testing")

        msg_dict = {"testing": True}
        topic_str = "testing"

        loop = asyncio.get_event_loop()
        has_message = False

        start = time.time()
        timeout = 10

        while not has_message:
            self.publisher.publish_message_multipart(topic_str=topic_str, msg_dict=msg_dict)
            has_message = loop.run_until_complete(self.subscriber.messages_waiting(timeout=100))

            if time.time() - start > timeout:
                self.fail("Test Case timed out waiting subscriber to get messages.")

        self.assertTrue(has_message)

    def test_METHOD_close_socket(self):
        self.subscriber.connect_socket()

        self.assertFalse(self.subscriber.socket_is_closed)
        self.subscriber.close_socket()
        self.async_sleep(1)
        self.assertTrue(self.subscriber.socket_is_closed)

    def test_METHOD_disconnect_socket__returns_if_socket_is_already_closed(self):
        self.subscriber.create_socket()

        #Close scoket before test
        self.subscriber.socket.close()
        self.async_sleep(1)

        self.subscriber.close_socket()
        self.async_sleep(1)
        self.assertTrue(self.subscriber.socket_is_closed)

    def test_METHOD_start__creates_check_for_messages_task(self):
        self.subscriber.start()

        self.async_sleep(0.5)

        self.assertFalse(self.subscriber.check_for_messages_task.done())

    def test_METHOD_stop_checking_for_messages__waits_for_task_to_end(self):
        self.start_subscriber()

        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.subscriber.stop_checking_for_messages())

        self.assertTrue(self.subscriber.check_for_messages_task.done())