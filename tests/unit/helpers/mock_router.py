from zmq.auth.thread import ThreadAuthenticator
import json
import threading
import zmq
import asyncio
import unittest

from lamden.crypto.wallet import Wallet

class MockCredentialsProvider(object):
    def __init__(self, valid_peers=[]):
        self.valid_peers = list(valid_peers)

    def callback(self, domain, key):
        print(domain)
        print(key)
        return key in self.valid_peers

class MockRouter(threading.Thread):
    def __init__(self, wallet, valid_peers=[], port=19000, callback=None):
        threading.Thread.__init__(self)
        self.daemon = True

        self.wallet = wallet
        self.port = port
        self.callback = callback

        self.ctx = None
        self.socket = None
        self.auth = None
        self.cred_provider = MockCredentialsProvider(valid_peers=valid_peers)

        self.poller = zmq.Poller()
        self.poll_time = 0.001

        self.running = False
        self.loop = None

        self.start()

    def setup_socket(self):
        self.ctx = zmq.Context()
        self.socket = self.ctx.socket(zmq.ROUTER)

        self.auth = ThreadAuthenticator(self.ctx)
        self.auth.start()
        self.auth.configure_curve_callback(domain="*", credentials_provider=self.cred_provider)

        self.poller.register(self.socket, zmq.POLLIN)

    def run(self):
        self.setup_socket()

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
                print("[ROUTER] Received request: ", msg)

                if self.callback:
                    self.callback(ident, msg)

                try:
                    msg_string = json.loads(msg)
                except Exception as err:
                    msg_string = None
                    print(err)

                if isinstance(msg_string, dict):
                    if msg_string.get('action') == 'hello':
                        resp_msg = json.dumps({'response': 'hello'}).encode('UTF-8')
                        self.send_msg(ident=ident, msg=resp_msg)

                    if msg_string.get('action') == 'latest_block_info':
                        resp_msg = json.dumps({
                            'response': 'latest_block_info',
                            'latest_block_number': 100,
                            'latest_hlc_timestamp': "1234"
                        }).encode('UTF-8')
                        self.send_msg(ident=ident, msg=resp_msg)

                    else:
                        self.send_msg(ident=ident, msg=msg)
                else:
                    self.send_msg(ident=ident, msg=msg)

            await asyncio.sleep(0)

        try:
            self.socket.setsockopt(zmq.LINGER, 0)
            self.auth.stop()
            self.socket.close()
            self.ctx.term()

        except zmq.ZMQError as err:
            self.log.error(f'[ROUTER] Error Stopping Socket: {err}')
            print(f'[{self.log.name}][ROUTER] Error Stopping Socket: {err}')
            pass

    def send_msg(self, ident: str, msg):
        self.socket.send_multipart([ident, b'', msg])

    async def stopping(self):
        self.running = False

        while not self.socket.closed:
            await asyncio.sleep(0.1)

    def stop(self):
        if self.running:
            self.running = False

        if self.socket:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.stopping())

        self.join()

class TestMockRouter(unittest.TestCase):
    def setUp(self) -> None:
        self.router = None

    def tearDown(self) -> None:
        del self.router

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def test_can_create_instance(self):
        self.router = MockRouter(
            wallet=Wallet(),
            valid_peers=[]
        )

        self.async_sleep(2)

        self.assertTrue(self.router.running)
        self.assertIsInstance(self.router, MockRouter)

        self.router.stop()
        self.async_sleep(1)

    def test_can_stop_instance(self):
        self.router = MockRouter(
            wallet=Wallet(),
            valid_peers=[]
        )
        self.async_sleep(2)
        self.router.stop()
        self.async_sleep(2)

        self.assertFalse(self.router.running)
        self.assertTrue(self.router.socket.closed)
