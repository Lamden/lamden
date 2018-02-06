from unittest import TestCase
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web

from cilantro.networking import Masternode
from cilantro.serialization import Serializer, JSONSerializer

from cilantro.networking.constants import MAX_REQUEST_LENGTH, TX_STATUS

import json


class MockSerializer(Serializer):
    @staticmethod
    def serialize(*args):
        return [arg for arg in args]

    @staticmethod
    def deserialize(*args):
        return [arg for arg in args]


class TestMasternode(TestCase):
    def setUp(self):
        self.host = '127.0.0.1'
        self.internal_port = '9999'
        self.external_port = '8080'
        self.serializer = JSONSerializer
        self.m = Masternode(host=self.host, internal_port=self.host, external_port=self.external_port,
                            serializer=self.serializer)

        # app = web.Application()
        # app.router.add_post('/', self.m.process_request)
        # web.run_app(app, host=self.m.host, port=int(self.m.external_port))
        # self.m.setup_web_server()

    def tearDown(self):
        pass
        # if hasattr(self.m, 'publisher'):
        #     self.m.publisher.unbind(self.m.url)
        # if hasattr(self.m, 'context'):
        #     self.m.context.term()

    def test_process_transaction_fields(self):
        """
        Tests that an error code is returned when a payload has invalid fields
        """
        payload_bad_fields = self.__dict_to_bytes({'payload': {'not to': 'some value'}})
        self.assertEquals(TX_STATUS['INVALID_TX_FIELDS'], self.m.process_transaction(data=payload_bad_fields))

    def test_process_transaction_size(self):
        """
        Tests that an error code is returned when a payload exceeds maximum size
        """
        payload_oversized = {'payload': {'to': 'satoshi', 'amount': '100', 'from': 'nakamoto'},
                             'metadata': {'sig': 'x287', 'proof': '000'}}
        for x in range(MAX_REQUEST_LENGTH + 2):
            payload_oversized['payload'][x] = "some key #" + str(x)
        self.assertEquals(TX_STATUS['INVALID_TX_SIZE'],
                          self.m.process_transaction(data=self.__dict_to_bytes(payload_oversized)))

    def test_process_transaction_valid(self):
        """
         Tests that a valid payload goes through
        """
        payload_valid = {'payload': {'to': 'satoshi', 'amount': '100', 'from': 'nakamoto'},
                         'metadata': {'sig': 'x287', 'proof': '000'}}
        self.assertEquals(TX_STATUS['SUCCESS']['status'].format(payload_valid),
                          self.m.process_transaction(data=self.__dict_to_bytes(payload_valid)))

    def __dict_to_bytes(self, d):
        return str.encode(json.dumps(d))

    def test_host_and_port_storage(self):
        HOST = '127.0.0.1'
        PORT = '9999'
        m = Masternode(host=HOST, internal_port=PORT)
        self.assertEqual(m.host, HOST)
        self.assertEqual(m.internal_port, PORT)

    def test_serialization_storage(self):
        m = Masternode(serializer=MockSerializer)
        self.assertEqual(type(m.serializer), type(MockSerializer))


class TestMasternodeAsync(AioHTTPTestCase):
    async def get_application(self):
        app = web.Application()
        app.router.add_post('/', Masternode().process_request)
        return app

    @unittest_run_loop
    async def test_web_server_setup(self):
        response = await self.client.request('POST', '/', data='{ "something" : "something else" }')
        print(response.status)
        print(await response.content.read())
        self.assertEqual(response.status, 200)
