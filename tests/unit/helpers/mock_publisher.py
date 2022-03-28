import zmq
import threading
import unittest
import asyncio
import json

class MockPublisher(threading.Thread):
    def __init__(self, port=19000):
        threading.Thread.__init__(self)
        self.daemon = True
        self.running = False

        self.ctx = None
        self.socket = None
        self.port = port

        self.start()

    def run(self):
        self.ctx = zmq.Context()
        self.running = True
        self.socket = self.ctx.socket(zmq.PUB)
        self.socket.bind(f'tcp://*:{self.port}')

        print(f'[PUBLISHER] Started.')

    def publish(self, topic, msg):
        print(f'[PUBLISHER] Publishing: {topic}')

        self.socket.send_string(topic, flags=zmq.SNDMORE)
        self.socket.send(json.dumps(msg).encode('utf-8'))

    def stop(self):
        if self.running:
            self.running = False
            self.socket.close()

            print(f'[PUBLISHER] Stopped.')

class TestMockPublisher(unittest.TestCase):
    def setUp(self) -> None:
        self.publisher = None

        self.message = json.dumps("TEST")

    def tearDown(self) -> None:
        if self.publisher:
            self.publisher.stop()

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

        while self.publisher.running:
            self.async_sleep(delay=0)

        self.assertFalse(self.publisher.running)

    def test_can_publish(self):
        self.start_publisher()
        self.publisher.publish(topic="TESTING")