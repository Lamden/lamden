import json
import asyncio

from lamden.crypto.wallet import Wallet
import unittest
import zmq
import threading
from time import sleep
from datetime import datetime
from zmq.auth.thread import ThreadAuthenticator

from lamden.sockets.request import Request

class MockCredentialsProvider(object):
    def callback(self, domain, key):
        True

class MockRouter(threading.Thread):
    def __init__(self, ctx, port=19000):
        threading.Thread.__init__(self)
        #self.daemon = True

        self.wallet = Wallet()
        self.port = port

        self.context = ctx
        self.socket = self.context.socket(zmq.ROUTER)
        self.cred_provider = MockCredentialsProvider()

        auth = ThreadAuthenticator(self.context)
        auth.start()
        auth.configure_curve_callback(domain="*", credentials_provider=self.cred_provider)

        self.poller = zmq.Poller()
        self.poller.register(self.socket, zmq.POLLIN)
        self.poll_time = 0.01

        self.running = False
        self.loop = None

        self.start()

    def run(self):

        self.socket.curve_secretkey = self.wallet.curve_sk
        self.socket.curve_publickey = self.wallet.curve_vk
        self.socket.curve_server = True  # must come before bind

        self.socket.bind(f"tcp://*:{self.port}")
        self.running = True

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.check_for_messages())

    async def check_for_messages(self):
        while self.running:
            sockets = dict(self.poller.poll(self.poll_time))
            # print(sockets[self.socket])
            if self.socket in sockets:
                ident, empty, msg = self.socket.recv_multipart()
                print("Received request: ", msg)
                self.send_msg(ident=ident, msg=msg)

            await asyncio.sleep(0)

        try:
            self.socket.close()
        except zmq.ZMQError as err:
            self.log.error(f'[ROUTER] Error Stopping Socket: {err}')
            print(f'[{self.log.name}][ROUTER] Error Stopping Socket: {err}')
            pass

    def send_msg(self, ident: str, msg):
        self.socket.send_multipart([ident, b'', msg])

    def stop(self):
        if self.running:
            self.running = False


class TestRequestSocket(unittest.TestCase):
    def setUp(self):
        self.ctx = zmq.Context()
        self.request_wallet = Wallet()
        self.router = MockRouter(ctx=self.ctx)

        self.request = Request(
            _id=self.request_wallet.verifying_key,
            _address='tcp://127.0.0.1:19000',
            peer_disconnected_callback=self.reconnect,
            server_vk=self.router.wallet.curve_vk,
            wallet=self.request_wallet,
            ctx=self.ctx
        )

        self.reconnect_called = False

    def tearDown(self):
        self.router.stop()
        self.request.stop()

    def await_async_process(self, process, args={}):
        tasks = asyncio.gather(
            process(**args)
        )
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)
        return res

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def reconnect(self):
        self.reconnect_called = True

    def test_can_create_instance_MOCKROUTER(self):
        self.assertIsInstance(obj=self.router, cls=MockRouter)

    def test_can_create_instance_REQUEST(self):
        self.assertIsInstance(obj=self.request, cls=Request)

    def test_can_stop_gracefully(self):
        # Can stop the socket and thread without errors
        self.request.stop()

    def test_send_msg_await(self):
        msg = json.dumps("ping")
        res = self.request.send_msg_await(msg=msg)
        print({"res.success": res.success})
        self.assertTrue(res.success)
        self.assertEqual(msg, res.response.decode('UTF-8'))

