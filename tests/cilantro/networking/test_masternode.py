from unittest import TestCase
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web

from cilantro.networking import Masternode
from cilantro.serialization import JSONSerializer

from cilantro.networking.constants import MAX_REQUEST_LENGTH, TX_STATUS

import json

class TestMasternode(TestCase):
    def setUp(self):
        self.host = '*'
        self.internal_port = '9999'
        self.external_port = '8080'
        self.serializer = JSONSerializer
        self.m = Masternode(host=self.host, internal_port=self.internal_port, external_port=self.external_port,
                            serializer=self.serializer)

    def tearDown(self):
        pass

    def test_process_transaction_fields(self):
        """
        Tests that an error code is returned when a payload has invalid fields
        """
        payload_bad_fields = TestMasternode.dict_to_bytes({'payload': {'not to': 'some value'}})
        # self.assertEquals(TX_STATUS['INVALID_TX_FIELDS'], self.m.process_transaction(data=payload_bad_fields))
        self.assertTrue('error' in self.m.process_transaction(data=payload_bad_fields))

    def test_process_transaction_size(self):
        """
        Tests that an error code is returned when a payload exceeds maximum size
        """
        payload_oversized = {'payload': {'to': 'satoshi', 'amount': '100', 'from': 'nakamoto', 'type':'t'},
                             'metadata': {'sig': 'x287', 'proof': '000'}}
        for x in range(MAX_REQUEST_LENGTH + 2):
            payload_oversized['payload'][x] = "some key #" + str(x)
        self.assertTrue('error' in self.m.process_transaction(data=TestMasternode.dict_to_bytes(payload_oversized)))


    def test_process_transaction_valid(self):
        """
         Tests that a valid payload goes through
        """
        payload_valid = {'payload': {'to': 'satoshi', 'amount': '100', 'from': 'nakamoto', 'type':'t'},
                         'metadata': {'sig': 'x287', 'proof': '000'}}
        self.assertTrue('success' in self.m.process_transaction(data=TestMasternode.dict_to_bytes(payload_valid)))
        # self.assertEqual(TX_STATUS['SUCCESS']['status'].format(payload_valid),
        #                  self.m.process_transaction(data=TestMasternode.dict_to_bytes(payload_valid)))

    def test_host_and_port_storage(self):
        self.assertEqual(self.m.host, self.host)
        self.assertEqual(self.m.internal_port, self.internal_port)
        self.assertEqual(self.m.external_port, self.external_port)

    def test_serialization_storage(self):
        self.assertEqual(type(self.m.serializer), type(self.serializer))

    @staticmethod
    def dict_to_bytes(d):
        return str.encode(json.dumps(d))


class TestMasternodeAsync(AioHTTPTestCase):
    async def get_application(self):
        app = web.Application()
        app.router.add_post('/', Masternode().process_request)
        return app

    @unittest_run_loop
    async def test_web_server_setup(self):
        payload = {'payload': {'to': 'satoshi', 'amount': '100', 'from': 'nakamoto'},
                                                      'metadata': {'sig': 'x287', 'proof': '000'}}
        payload_bytes = TestMasternode.dict_to_bytes(payload)
        response = await self.client.request('POST', '/', data=payload_bytes)
        response_data = await response.content.read()
        # response_data = response_data_bytes.decode()
        self.assertEqual(response_data.decode(), TX_STATUS['SUCCESS']['status'].format(payload))
        self.assertEqual(response.status, 200)
