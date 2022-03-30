import zmq
import unittest
import json

class MockPublisher():
    def __init__(self, port=19000):
        self.running = False

        self.ctx = None
        self.socket = None
        self.port = port

        self.start()

    def start(self):
        self.ctx = zmq.Context()

        self.socket = self.ctx.socket(zmq.PUB)
        self.socket.bind(f'tcp://*:{self.port}')

        print(f'[PUBLISHER] Started...')
        self.running = True


    def publish(self, topic, msg):
        print(f'[PUBLISHER] Publishing: {topic}')

        self.socket.send_string(topic, flags=zmq.SNDMORE)
        self.socket.send(json.dumps(msg).encode('utf-8'))

    def stop(self):
        if self.running:
            self.running = False
            if self.socket:
                self.socket.setsockopt(zmq.LINGER, 0)
                self.socket.close()
                self.ctx.term()

            print(f'[PUBLISHER] Stopped...')

class TestMockPublisher(unittest.TestCase):
    def setUp(self) -> None:
        self.publisher = None

        self.message = json.dumps("TEST")

    def tearDown(self) -> None:
        if self.publisher:
            self.publisher.stop()
            del self.publisher

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

    def test_can_publish(self):
        self.start_publisher()
        self.publisher.publish(topic="TESTING", msg="TESTING")