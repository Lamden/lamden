from unittest import TestCase
from cilantro.networking import BaseNode
from cilantro.serialization import JSONSerializer
import asyncio
import time

class MockBaseNode(BaseNode):
    def handle_req(self, data: bytes):
        if data == b'999':
            self.disconnect()


class TestBaseNode(TestCase):
    def setUp(self):
        self.base_url = '127.0.0.1'
        self.subscriber_port = 8888
        self.publisher_port = 7777
        self.serializer = JSONSerializer

        self.b = MockBaseNode(base_url=self.base_url,
                              subscriber_port=self.subscriber_port,
                              publisher_port=self.publisher_port,
                              serializer=self.serializer)

    def tearDown(self):
        self.b.terminate()

    def test_basenode_init(self):
        self.assertEqual(self.b.message_queue.base_url, self.base_url)
        self.assertEqual(self.b.message_queue.subscriber_port, self.subscriber_port)
        self.assertEqual(self.b.message_queue.publisher_port, self.publisher_port)
        self.assertEqual(self.b.serializer, JSONSerializer)

    async def test_vanilla_zmq_loop(self):
        try:
            await self.b.zmq_loop()
            self.assertTrue(False)
        except NotImplementedError:
            self.assertTrue(True)

    async def test_vanilla_mp_loop(self):
        try:
            await self.b.mp_loop()
            self.assertTrue(False)
        except NotImplementedError:
            self.assertTrue(True)

    def test_send_json(self):
        test_json = {
            'something': 'something'
        }
        time.sleep(1)
        response = self.b.publish_req(test_json)
        self.assertEqual(response['status'], "Successfully published request: {'something': 'something'}")

    def test_send_bad_json(self):
        self.b.start_listening()
        test_json = b'd34db33f'

        try:
            self.b.publish_req(test_json)
            self.assertEqual(1, 2)
        except Exception as e:
            self.assertEqual(1, 1)

        self.b.disconnect()

    def test_listen(self):
        self.assertEqual(self.b.ctx, None)
        self.b.start_listening()
        print('ass')
        self.b.disconnect()
