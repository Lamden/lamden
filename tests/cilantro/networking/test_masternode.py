from unittest import TestCase
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web

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