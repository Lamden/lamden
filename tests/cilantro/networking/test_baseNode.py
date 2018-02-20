from unittest import TestCase
from cilantro.networking import BaseNode
from cilantro.serialization import JSONSerializer
import asyncio

class MockBaseNode(BaseNode):
    def handle_req(self, data: bytes):
        if data == b'999':
            self.disconnect()


class TestBaseNode(TestCase):
    def setUp(self):
        self.host = '127.0.0.1'
        self.sub_port = 8888
        self.pub_port = 7777
        self.serializer = JSONSerializer

        self.b = MockBaseNode(host=self.host, sub_port=self.sub_port, pub_port=self.pub_port, serializer=self.serializer)

    def test_sanity(self):
        self.assertEqual(1, 1)

    def test_basenode_init(self):
        self.assertEqual(self.b.host, self.host)
        self.assertEqual(self.b.sub_port, self.sub_port)
        self.assertEqual(self.b.pub_port, self.pub_port)
        self.assertEqual(self.b.serializer, JSONSerializer)

    def test_send_json(self):
        self.b.start_listening()
        test_json = {
            'something' : 'something'
        }

        response = self.b.publish_req(test_json)
        self.assertEqual(response['status'], "Successfully published request: {'something': 'something'}")
        self.b.disconnect()

    def test_send_bad_json(self):
        self.b.start_listening()
        test_json = b'd34db33f'

        try:
            self.b.publish_req(test_json)
            self.assertEqual(1, 2)
        except Exception as e:
            self.assertEqual(1, 1)

        from contextlib import suppress
        from zmq.error import ContextTerminated
        with suppress(Exception):
            self.b.disconnect()

    def test_listen(self):
        self.assertEqual(self.b.ctx, None)
        self.b.start_listening()
        print('ass')
        self.b.disconnect()