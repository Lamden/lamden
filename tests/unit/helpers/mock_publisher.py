import zmq
import zmq.asyncio
import asyncio
import unittest
import json

class MockPublisher():
    def __init__(self, port=19080):
        self.running = False

        self.ctx = None
        self.socket = None
        self.port = port

        self.start()


    def start(self):
        self.ctx = zmq.asyncio.Context()

        self.socket = self.ctx.socket(zmq.PUB)

        #self.socket.connect(f'tcp://127.0.0.1:{self.port}')
        self.socket.bind(f'tcp://*:{self.port}')

        print(f'[PUBLISHER] Started...')
        self.running = True


    def publish_message_multipart(self, topic_str: str, msg_dict: dict) -> None:
        try:
            msg_bytes = json.dumps(msg_dict).encode('UTF-8')
            self.socket.send_multipart([topic_str.encode('UTF-8'), msg_bytes])
        except Exception as err:
            print(err)

    def publish_message_bytes(self, msg_bytes: bytes) -> None:
        self.socket.send(msg_bytes)

    def publish_message_str(self, msg_str: str) -> None:
        self.socket.send_string(msg_str)

    def stop(self):
        if self.running:
            self.running = False
            if self.socket:
                self.socket.setsockopt(zmq.LINGER, 0)
                self.socket.close()

            self.ctx.destroy()

            print(f'[PUBLISHER] Stopped...')

class TestMockPublisher(unittest.TestCase):
    def setUp(self) -> None:
        self.publisher = None

        self.message = json.dumps("TEST")

    def tearDown(self) -> None:
        if self.publisher:
            self.publisher.stop()
            del self.publisher

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def start_publisher(self):
        self.publisher = MockPublisher()

    def test_can_create_instance__MOCKPUBLISHER(self):
        self.start_publisher()
        self.assertIsInstance(self.publisher, MockPublisher)
        self.assertTrue(self.publisher.running)

    def test_can_create_instance__MOCKPUBLISHER_stops(self):
        self.start_publisher()
        self.assertIsNotNone(self.publisher)
        self.assertTrue(self.publisher.running)

        try:
            self.publisher.stop()
        except Exception:
            self.fail("Request did not stop cleanly!")

        self.assertFalse(self.publisher.running)

    def test_can_publish_string(self):
        ctx = zmq.asyncio.Context().instance()
        loop = asyncio.get_event_loop()

        self.start_publisher()
        self.async_sleep(1)

        sub = ctx.socket(zmq.SUB)
        sub.setsockopt(zmq.SUBSCRIBE, b'')

        sub.bind('tcp://127.0.0.1:19080')
        asyncio.ensure_future(sub.poll(timeout=1))

        self.async_sleep(1)

        message_str = 'testing'
        self.publisher.publish_message_str(message_str)
        self.async_sleep(1)

        event = 0
        while not event:
            event = loop.run_until_complete(sub.poll(timeout=50))
            self.async_sleep(1)

        res = loop.run_until_complete(sub.recv_multipart())
        sub.close(linger=10)

        message_received = res[0].decode('UTF-8')
        self.assertEqual(message_str, message_received)

    def test_can_publish_bytes(self):
        ctx = zmq.asyncio.Context().instance()
        loop = asyncio.get_event_loop()

        self.start_publisher()
        self.async_sleep(1)

        sub = ctx.socket(zmq.SUB)
        sub.setsockopt(zmq.SUBSCRIBE, b'')

        sub.bind('tcp://127.0.0.1:19080')
        asyncio.ensure_future(sub.poll(timeout=1))

        self.async_sleep(1)

        msg_bytes = 'testing'.encode('UTF-8')
        self.publisher.publish_message_bytes(msg_bytes=msg_bytes)
        self.async_sleep(1)

        event = 0
        while not event:
            event = loop.run_until_complete(sub.poll(timeout=50))
            self.async_sleep(1)

        res = loop.run_until_complete(sub.recv_multipart())
        sub.close(linger=10)

        message_received = res[0]
        self.assertEqual(msg_bytes, message_received)

    def test_can_publish_multipart(self):
        ctx = zmq.asyncio.Context().instance()
        loop = asyncio.get_event_loop()

        self.start_publisher()
        self.async_sleep(1)

        sub = ctx.socket(zmq.SUB)
        sub.setsockopt(zmq.SUBSCRIBE, b'')
        sub.setsockopt(zmq.SUBSCRIBE, b'testing')

        sub.bind('tcp://127.0.0.1:19080')
        asyncio.ensure_future(sub.poll(timeout=1))

        self.async_sleep(1)

        topic = 'testing'
        msg_dict = {'testing': True}

        self.publisher.publish_message_multipart(topic_str=topic, msg_dict=msg_dict)
        self.async_sleep(1)

        event = 0
        while not event:
            event = loop.run_until_complete(sub.poll(timeout=50))
            self.async_sleep(1)

        message_received = loop.run_until_complete(sub.recv_multipart())
        sub.close(linger=10)

        message_received

        self.assertEqual(topic, message_received[0].decode('UTF-8'))
        self.assertEqual(msg_dict, json.loads(message_received[1]))


