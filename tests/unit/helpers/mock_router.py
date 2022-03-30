from zmq.auth.thread import ThreadAuthenticator
import threading
import zmq
import asyncio

class MockCredentialsProvider(object):
    def __init__(self, valid_peers=[]):
        self.valid_peers = valid_peers

    def callback(self, domain, key):
        return key in self.valid_peers

class MockRouter(threading.Thread):
    def __init__(self, wallet, valid_peers=[], port=19000):
        threading.Thread.__init__(self)
        self.daemon = True

        self.wallet = wallet
        self.port = port

        self.ctx = None
        self.socket = None
        self.cred_provider = MockCredentialsProvider(valid_peers=valid_peers)

        self.poller = zmq.Poller()
        self.poll_time = 0.01

        self.running = False
        self.loop = None

        self.start()

    def setup_socket(self):
        self.ctx = zmq.Context()
        self.socket = self.ctx.socket(zmq.ROUTER)

        auth = ThreadAuthenticator(self.ctx)
        auth.start()
        auth.configure_curve_callback(domain="*", credentials_provider=self.cred_provider)

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
                print("Received request: ", msg)
                self.send_msg(ident=ident, msg=msg)

            await asyncio.sleep(0)

        try:
            self.socket.setsockopt(zmq.LINGER, 0)
            self.socket.close()
            self.ctx.term()
        except zmq.ZMQError as err:
            self.log.error(f'[ROUTER] Error Stopping Socket: {err}')
            print(f'[{self.log.name}][ROUTER] Error Stopping Socket: {err}')
            pass

    def send_msg(self, ident: str, msg):
        self.socket.send_multipart([ident, b'', msg])

    def stop(self):
        if self.running:
            self.running = False