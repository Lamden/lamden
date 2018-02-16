from cilantro.networking import Masternode2
from cilantro.serialization import JSONSerializer
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
import json



class TestMasternodeAsync(AioHTTPTestCase):
    def setUp(self):
        self.host = '127.0.0.1'
        self.internal_port = '7777'
        self.external_port = '8888'
        self.serializer = JSONSerializer

        self.mn = Masternode2(host=self.host, external_port=self.external_port, internal_port=self.internal_port)

    def tearDown(self):
        pass

    async def get_application(self):
        app = web.Application()
        app.router.add_post('/', Masternode2().process_request)
        return app

    @unittest_run_loop
    async def test_web_server_setup(self):
        payload = {'payload': {'to': 'satoshi', 'amount': '100', 'from': 'nakamoto'},
                                                      'metadata': {'sig': 'x287', 'proof': '000'}}
        # payload = {"payload": {"to": "kevin”", "amount": "900", "from": "davis", "type": "t"}, "metadata": {"sig": "0x123", "proof": "c75ea80f6aa92f078e10a6b4837fac62"}}
        payload_bytes = TestMasternodeAsync.dict_to_bytes(payload)

        self.mn.set_up_web_Server()

        response = await self.client.request('POST', '/', data=payload_bytes)
        response_data = await response.content.read()
        # response_data = response_data_bytes.decode()
        # self.assertEqual(response_data.decode(), TX_STATUS['SUCCESS']['status'].format(payload))
        self.assertEqual(response.status, 200)

    @staticmethod
    def dict_to_bytes(d):
        return str.encode(json.dumps(d))