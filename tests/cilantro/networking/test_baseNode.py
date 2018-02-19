from unittest import TestCase
from cilantro.networking import BaseNode
from cilantro.serialization import JSONSerializer


class TestBaseNode(TestCase):
    def setUp(self):
        self.host = '127.0.0.1'
        self.sub_port = 8888
        self.pub_port = 7777
        self.serializer = JSONSerializer

        self.b = BaseNode(host=self.host, sub_port=self.sub_port, pub_port=self.pub_port, serializer=self.serializer)

    def tearDown(self):
        self.b.disconnect()

    def test_sanity(self):
        self.assertEqual(1, 1)

    def test_basenode_init(self):
        self.assertEqual(self.b.host, self.host)
        self.assertEqual(self.b.sub_port, self.sub_port)
        self.assertEqual(self.b.pub_port, self.pub_port)
        self.assertEqual(self.b.serializer, JSONSerializer)

    def test_send_json(self):
        test_json = {
            'something' : 'something'
        }

        response = self.b.publish_req(test_json)
        self.assertEqual(response['status'], "Successfully published request: {'something': 'something'}")

    def test_send_bad_json(self):
        test_json = b'd34db33f'

        try:
            self.b.publish_req(test_json)
            self.assertEqual(1, 2)
        except Exception as e:
            self.assertEqual(1, 1)




