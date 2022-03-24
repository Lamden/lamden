import json
import asyncio

from lamden.crypto.wallet import Wallet
import unittest
import zmq
import threading
from time import sleep
from datetime import datetime
import time
from zmq.auth.thread import ThreadAuthenticator

from lamden.sockets.request import Request

class MockCredentialsProvider(object):
    def __init__(self, valid_peers=[]):
        self.valid_peers = valid_peers

    def callback(self, domain, key):
        return key in self.valid_peers

class MockRouter(threading.Thread):
    def __init__(self, ctx, wallet, valid_peers=[], port=19000):
        threading.Thread.__init__(self)
        self.daemon = True

        self.wallet = wallet
        self.port = port

        self.context = ctx
        self.socket = self.context.socket(zmq.ROUTER)
        self.cred_provider = MockCredentialsProvider(valid_peers=valid_peers)

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


class MockReply(threading.Thread):
    def __init__(self, ctx, port=19000):
        threading.Thread.__init__(self)
        self.daemon = True

        self.wallet = Wallet()
        self.port = port

        self.context = ctx
        self.socket = self.context.socket(zmq.REP)

        self.poller = zmq.Poller()
        self.poller.register(self.socket, zmq.POLLIN)
        self.poll_time = 0.01

        self.running = False
        self.loop = None

        self.start()

    def run(self):
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
                msg = self.socket.recv()
                print("Received request: ", msg)
                self.send_msg(msg=msg)

            await asyncio.sleep(0)

        try:
            self.socket.close()
        except zmq.ZMQError as err:
            self.log.error(f'[ROUTER] Error Stopping Socket: {err}')
            print(f'[{self.log.name}][ROUTER] Error Stopping Socket: {err}')
            pass

    def send_msg(self, msg):
        self.socket.send(msg)

    def stop(self):
        if self.running:
            self.running = False

class TestRequestSocket(unittest.TestCase):
    def setUp(self):
        self.ctx = zmq.Context()
        self.request_wallet = Wallet()
        self.peer_wallet = Wallet()

        self.peer_address = 'tcp://127.0.0.1:19000'
        self.peer = None
        self.request = None

        self.reconnect_called = False
        self.ping_msg = json.dumps("ping")

    def tearDown(self):
        if self.peer:
            self.peer.stop()
        if self.request:
            self.request.stop()

    def start_secure_peer(self):
        self.peer = MockRouter(
            valid_peers=[self.request_wallet.curve_vk],
            wallet=self.peer_wallet,
            ctx=self.ctx,
        )

    def start_peer(self):
        self.peer = MockReply(ctx=self.ctx)

    def create_secure_request(self):
        self.request = Request(
            server_vk=self.peer_wallet.curve_vk,
            wallet=self.request_wallet,
            ctx=self.ctx
        )

    def create_request(self):
        self.request = Request(ctx=self.ctx)

    async def wrap_process_in_async(self, process, args={}):
        process(**args)

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
        self.start_secure_peer()
        self.assertIsInstance(obj=self.peer, cls=MockRouter)

    def test_can_create_instance_MOCKREPLY(self):
        self.start_peer()
        self.assertIsInstance(obj=self.peer, cls=MockReply)

    def test_can_create_instance_REQUEST(self):
        self.create_request()
        self.assertIsInstance(obj=self.request, cls=Request)

    def test_can_create_instance_secure_REQUEST(self):
        self.create_secure_request()
        self.assertIsInstance(obj=self.request, cls=Request)
        self.assertTrue(self.request.secure_socket)

    def test_send_msg_get_successful_response(self):
        self.start_peer()
        self.create_request()

        res = self.request.send(to_address=self.peer_address, msg=self.ping_msg)
        asyncio.sleep(50)

        self.assertTrue(res.success)
        self.assertIsNone(res.error)
        self.assertIsNotNone(res.response)

        self.assertEqual(self.ping_msg, res.response.decode('UTF-8'))

    def test_send_msg_msg_no_receiver(self):
        self.create_request()

        retries = 3
        timeout = 500
        res = self.request.send(to_address=self.peer_address, msg=self.ping_msg, retries=retries, timeout=timeout)

        self.assertFalse(res.success)
        error = f"Request Socket Error: Failed to receive response after {retries} attempts each waiting {timeout}ms"

        self.assertEquals(error, res.error)
        self.assertIsNone(res.response)

        self.request.stop()

        print("STOP")


    def test_send_secure_msg_get_successful_response(self):
        self.start_secure_peer()
        self.create_secure_request()

        res = self.request.send(to_address=self.peer_address, msg=self.ping_msg)

        self.assertTrue(res.success)
        self.assertIsNone(res.error)
        self.assertIsNotNone(res.response)

        self.assertEqual(self.ping_msg, res.response.decode('UTF-8'))

        self.peer.stop()

    def test_send_secure_msg_no_receiver(self):
        self.create_secure_request()

        retries = 3
        timeout = 500
        res = self.request.send(to_address=self.peer_address, msg=self.ping_msg, retries=retries, timeout=timeout)

        self.assertFalse(res.success)
        error = f"Request Socket Error: Failed to receive response after {retries} attempts each waiting {timeout}ms"
        self.assertEquals(error, res.error)
        self.assertIsNone(res.response)

    def test_can_stop_if_socket_is_None(self):
        # Does not throw exceptions or hang
        self.create_request()

        try:
            self.request.stop()
        except Exception:
            self.fail("Request did not stop cleanly!")

    def test_can_stop_if_socket_exists(self):
        self.create_request()

        # Does not throw exceptions or hang
        self.request.create_socket()
        try:
            self.request.stop()
        except Exception:
            self.fail("Request did not stop cleanly!")





