from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web

from cilantro.networking import Masternode2, Witness2

class MyAppTestCase(AioHTTPTestCase):

    async def get_application(self):
        """
        Override the get_app method to return your application.
        """
        async def hello(request):
            return web.Response(text='Hello, world')

        app = web.Application()
        app.router.add_get('/', hello)
        return app

    # the unittest_run_loop decorator can be used in tandem with
    # the AioHTTPTestCase to simplify running
    # tests that are asynchronous
    @unittest_run_loop
    async def test_example(self):
        request = await self.client.request("GET", "/")
        assert request.status == 200
        text = await request.text()
        assert "Hello, world" in text

    # a vanilla example
    def test_example_vanilla(self):
        async def test_get_route():
            url = "/"
            resp = await self.client.request("GET", url)
            assert resp.status == 200
            text = await resp.text()
            assert "Hello, world" in text

        self.loop.run_until_complete(test_get_route())


class TestWitness(AioHTTPTestCase):

    def setUp(self):
        self.mn = Masternode2()
        self.host = '127.0.0.1'
        self.sub_port = '8888'
        self.pub_port = '8080'
        self.w = Witness2(sub_port=self.sub_port, pub_port=self.pub_port)


    async def get_application(self):
        """
        Override the get_app method to return your application.
        Basically this is setup_web_server
        """
        app = web.Application()
        app.router.add_post('/', self.mn.process_request)
        # app.router.add_get('/', hello)
        return app

