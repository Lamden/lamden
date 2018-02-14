from unittest import TestCase
from cilantro.serialization import JSONSerializer
from cilantro.networking.constants import MAX_REQUEST_LENGTH, TX_STATUS

from cilantro.networking import Masternode2
import json

class TestMasternode2(TestCase):
    def setUp(self):
        self.host = '127.0.0.1'
        self.internal_port = '7777'
        self.external_port = '8888'
        self.serializer = JSONSerializer

        self.mn = Masternode2(host=self.host, external_port=self.external_port, internal_port=self.internal_port)

    def tearDown(self):
        """
        1) Disconnects the pub_socket that was initialized when self.mn was initalized
        2) ctx destroy closes all sockets associated with the Master node's zmq's Context
        :return:
        """
        self.mn.pub_socket.disconnect(self.mn.pub_url)
        self.mn.ctx.destroy()

    def test_process_transaction_fields(self):
        """
        Tests that an error code is returned when a payload has invalid fields
        """
        payload_bad_fields = TestMasternode2.dict_to_bytes({'payload': {'not to': 'some value'}})
        self.assertTrue('error' in self.mn.process_transaction(data=payload_bad_fields))

    def test_process_transaction_size(self):
        """
        Tests that an error code is returned when a payload exceeds maximum size
        """
        payload_oversized = {'payload': {'to': 'satoshi', 'amount': '100', 'from': 'nakamoto', 'type':'t'},
                             'metadata': {'sig': 'x287', 'proof': '000'}}
        for x in range(MAX_REQUEST_LENGTH + 2):
            payload_oversized['payload'][x] = "some key #" + str(x)
        self.assertTrue('error' in self.mn.process_transaction(data=TestMasternode2.dict_to_bytes(payload_oversized)))

    def test_process_transaction_valid(self):
        """
         Tests that a valid payload goes through
        """
        payload_valid = {'payload': {'to': 'satoshi', 'amount': '100', 'from': 'nakamoto', 'type':'t'},
                         'metadata': {'sig': 'x287', 'proof': '000'}}
        self.assertTrue('success' in self.mn.process_transaction(data=TestMasternode2.dict_to_bytes(payload_valid)))

    def test_host_and_port_storage(self):
        self.assertEqual(self.mn.host, self.host)
        self.assertEqual(self.mn.pub_port, self.internal_port)
        self.assertEqual(self.mn.external_port, self.external_port)
        self.assertEqual(self.mn.sub_port, None)

    def test_serialization_storage(self):
        self.assertEqual(type(self.mn.serializer), type(self.serializer))

    @staticmethod
    def dict_to_bytes(d):
        return str.encode(json.dumps(d))