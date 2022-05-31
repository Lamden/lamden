from zmq.auth.thread import ThreadAuthenticator
import json
import threading
import zmq
import zmq.asyncio
import asyncio
import unittest
from contracting.db.encoder import encode

from lamden.crypto.wallet import Wallet

class MockCredentialsProvider(object):
    def __init__(self, valid_peers=[]):
        self.valid_peers = list(valid_peers)

    def callback(self, domain, key):
        print(domain)
        print(key)
        return key in self.valid_peers

class MockRouter(threading.Thread):
    def __init__(self, wallet, valid_peers=[], port=19000, message_callback=None):
        threading.Thread.__init__(self)
        self.daemon = True

        self.wallet = wallet
        self.port = port
        self.message_callback = message_callback

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

                if self.message_callback:
                    self.message_callback(ident_vk_string=json.loads(ident), msg=msg)

                try:
                    msg_obj = json.loads(msg)
                except Exception as err:
                    self.send_msg(ident=ident, msg=msg)

                action = msg_obj.get('action')

                if action not in ['ping', 'hello', 'latest_block_info']:
                    self.send_msg(ident=ident, msg=msg)
                else:
                    if action == 'ping':
                        resp_msg = json.dumps({
                            'response': 'ping'
                        }).encode('UTF-8')

                    if action == 'hello':
                        challenge = msg_obj.get('challenge')
                        if challenge:
                            challenge_response = self.wallet.sign(challenge)
                            resp_msg = json.dumps(
                                {
                                    'response': 'hello',
                                    'challenge_response': challenge_response,
                                    'latest_block_number': 1,
                                    'latest_hlc_timestamp': "1"
                                }).encode('UTF-8')
                        else:
                            resp_msg = json.dumps({'response': 'hello'}).encode('UTF-8')

                    if action == 'latest_block_info':
                        resp_msg = json.dumps({
                            'response': 'latest_block_info',
                            'latest_block_number': 100,
                            'latest_hlc_timestamp': "1234"
                        }).encode('UTF-8')

                    self.send_msg(ident=ident, msg=resp_msg)

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

class TestMockRouter(unittest.TestCase):
    def setUp(self) -> None:
        self.router = None
        self.request_wallet = Wallet()
        self.router_wallet = Wallet()

        self.responses = dict()

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
            wallet=self.router_wallet,
            valid_peers=[]
        )

        self.async_sleep(2)

        self.assertTrue(self.router.running)
        self.assertIsInstance(self.router, MockRouter)

        self.router.stop()
        self.async_sleep(1)

    def test_can_stop_instance(self):
        self.router = MockRouter(
            wallet=self.router_wallet,
            valid_peers=[]
        )
        self.async_sleep(2)
        self.router.stop()
        self.async_sleep(2)

        self.assertFalse(self.router.running)
        self.assertTrue(self.router.socket.closed)

    def test_SCENARIO_router_can_receive_multiple_messages_from_a_request_socket__SAME_SOCKET_ONE_BY_ONE(self):
        def router_callback(ident_vk_string: str, msg: str) -> None:
            print("ROUTER CALLBACK")
            if self.responses.get(ident_vk_string) is None:
                self.responses[ident_vk_string] = 1
            else:
                self.responses[ident_vk_string] += 1

        async def send_request(socket, pollin):
            response = None
            ping_msg = json.dumps({'action': 'ping'})
            socket.send_string(ping_msg)
            sockets = await pollin.poll(1000)
            if socket in dict(sockets):
                res = await socket.recv()
                response = res.decode('UTF-8')
                print(f'response: {response}')

            return response

        self.router = MockRouter(
            wallet=self.router_wallet,
            valid_peers=[self.request_wallet.curve_vk],
            message_callback=router_callback
        )

        self.async_sleep(1)

        self.router.message_callback = router_callback
        router_address = 'tcp://127.0.0.1:19000'

        ctx = zmq.asyncio.Context()
        socket = ctx.socket(zmq.REQ)

        socket.curve_secretkey = self.request_wallet.curve_sk
        socket.curve_publickey = self.request_wallet.curve_vk
        socket.curve_serverkey = self.router_wallet.curve_vk
        socket.identity = encode(self.request_wallet.verifying_key).encode()
        pollin = zmq.asyncio.Poller()
        pollin.register(socket, zmq.POLLIN)
        socket.connect(router_address)

        num_of_messages = 10
        task_list = list()
        for i in range(num_of_messages):
            task = asyncio.ensure_future(
                send_request(socket=socket, pollin=pollin)
            )
            task_list.append(task)
            loop = asyncio.get_event_loop()
            loop.run_until_complete(task)
            self.async_sleep(1)

        tasks = asyncio.gather(*task_list)
        loop = asyncio.get_event_loop()
        task_results = loop.run_until_complete(tasks)
        task_results_decoded = [json.loads(result) for result in task_results]

        socket.close()
        pollin.unregister(socket)

        self.assertEqual(num_of_messages, self.responses.get(self.request_wallet.verifying_key))
        ping_responses = [result.get('response') == "ping" for result in task_results_decoded]
        passed = all(ping_responses)
        self.assertTrue(passed)

    def test_SCENARIO_router_can_receive_multiple_messages_from_a_request_socket__DISPOSABLE_REQUEST_SOCKETS_ONE_BY_ONE(self):
        def router_callback(ident_vk_string: str, msg: str) -> None:
            print("ROUTER CALLBACK")
            if self.responses.get(ident_vk_string) is None:
                self.responses[ident_vk_string] = 1
            else:
                self.responses[ident_vk_string] += 1

        async def send_request():
            response = None

            router_address = 'tcp://127.0.0.1:19000'

            ctx = zmq.asyncio.Context()
            socket = ctx.socket(zmq.REQ)

            socket.curve_secretkey = self.request_wallet.curve_sk
            socket.curve_publickey = self.request_wallet.curve_vk
            socket.curve_serverkey = self.router_wallet.curve_vk
            socket.identity = encode(self.request_wallet.verifying_key).encode()
            pollin = zmq.asyncio.Poller()
            pollin.register(socket, zmq.POLLIN)
            socket.connect(router_address)

            ping_msg = json.dumps({'action': 'ping'})
            socket.send_string(ping_msg)
            sockets = await pollin.poll(1000)
            if socket in dict(sockets):
                res = await socket.recv()
                response = res.decode('UTF-8')
                print(f'response: {response}')

            socket.close()
            pollin.unregister(socket)

            return response

        self.router = MockRouter(
            wallet=self.router_wallet,
            valid_peers=[self.request_wallet.curve_vk],
            message_callback=router_callback
        )

        self.async_sleep(1)

        self.router.message_callback = router_callback

        task_list = list()
        num_of_messages = 10
        for i in range(num_of_messages):
            task = asyncio.ensure_future(
                send_request()
            )
            task_list.append(task)
            loop = asyncio.get_event_loop()
            loop.run_until_complete(task)
            self.async_sleep(1)

        tasks = asyncio.gather(*task_list)
        loop = asyncio.get_event_loop()
        task_results = loop.run_until_complete(tasks)
        task_results_decoded = [json.loads(result) for result in task_results]

        self.assertEqual(num_of_messages, self.responses.get(self.request_wallet.verifying_key))
        ping_responses = [result.get('response') == "ping" for result in task_results_decoded]
        passed = all(ping_responses)
        self.assertTrue(passed)

    def test_SCENARIO_router_can_receive_multiple_messages_from_a_request_socket__DISPOSABLE_REQUEST_SOCKETS_AT_ONCE(self):
        '''
            THIS TEST CASE WILL FAIL!!!
            FINDING OUT WHY THE ROUTER CANNOT ACCEPT REQUESTS ASYNC NEEDS TO BE DETERMINED.
        :return:
        '''

        def router_callback(ident_vk_string: str, msg: str) -> None:
            print("ROUTER CALLBACK")
            if self.responses.get(ident_vk_string) is None:
                self.responses[ident_vk_string] = 1
            else:
                self.responses[ident_vk_string] += 1

        async def send_request():
            router_address = 'tcp://127.0.0.1:19000'
            response = None

            ctx = zmq.asyncio.Context()
            socket = ctx.socket(zmq.REQ)

            socket.curve_secretkey = self.request_wallet.curve_sk
            socket.curve_publickey = self.request_wallet.curve_vk
            socket.curve_serverkey = self.router_wallet.curve_vk
            socket.identity = encode(self.request_wallet.verifying_key).encode()
            pollin = zmq.asyncio.Poller()
            pollin.register(socket, zmq.POLLIN)
            socket.connect(router_address)

            ping_msg = json.dumps({'action': 'ping'})
            socket.send_multipart([ping_msg.encode('UTF-8')])

            sockets = await pollin.poll(100)
            if socket in dict(sockets):
                res = await socket.recv()
                response = res.decode('UTF-8')
                print(f'response: {response}')

            socket.close()
            pollin.unregister(socket)

            return response

        self.router = MockRouter(
            wallet=self.router_wallet,
            valid_peers=[self.request_wallet.curve_vk],
            message_callback=router_callback
        )
        self.async_sleep(1)

        self.router.message_callback = router_callback
        num_of_messages = 20
        task_list = list()
        for i in range(num_of_messages):
            task = asyncio.ensure_future(
                send_request()
            )
            task_list.append(task)

        tasks = asyncio.gather(*task_list)
        loop = asyncio.get_event_loop()
        task_results = loop.run_until_complete(tasks)
        task_results_decoded = [json.loads(result) for result in task_results]

        self.assertEqual(num_of_messages, self.responses.get(self.request_wallet.verifying_key))
        ping_responses = [result.get('response') == "ping" for result in task_results_decoded]
        passed = all(ping_responses)
        self.assertTrue(passed)
