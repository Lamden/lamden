from unittest import TestCase
from cilantro.networking import Masternode
from cilantro.serialization import Serializer

class MockSerializer(Serializer):
    @staticmethod
    def serialize(*args):
        return [arg for arg in args]

    @staticmethod
    def deserialize(*args):
        return [arg for arg in args]

class TestMasternode(TestCase):
    def test_host_and_port_storage(self):
        HOST = '127.0.0.1'
        PORT = '9999'
        m = Masternode(host=HOST, internal_port=PORT)
        self.assertEqual(m.host, HOST)
        self.assertEqual(m.internal_port, PORT)

    def test_serialization_storage(self):
        m = Masternode(serializer=MockSerializer)
        self.assertEqual(type(m.serializer), type(MockSerializer))