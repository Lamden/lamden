import zmq
import json
from lamden.crypto.wallet import Wallet
from zmq.auth.asyncio import AsyncioAuthenticator
import asyncio


class Publisher:
    def __init__(self, socket_id, ctx: zmq.Context, wallet=None, linger=1000, poll_timeout=50):
        if socket_id.startswith('tcp'):
            _, _, port = socket_id.split(':')
            self.address = f'tcp://*:{port}'
        else:
            self.address = socket_id

        self.ctx = ctx
        self.wallet = wallet
        self.linger = linger
        self.poll_timeout = poll_timeout

        self.socket = None

    def setup_socket(self):
        self.socket = self.ctx.socket(zmq.PUB)

        self.socket.setsockopt(zmq.CURVE_PUBLICKEY, self.wallet.curve_vk)
        self.socket.setsockopt(zmq.CURVE_SECRETKEY, self.wallet.curve_sk)
        self.socket.setsockopt(zmq.CURVE_SERVER, True)

        self.socket.bind(self.address)

    def publish(self, topic, msg):
        m = json.dumps(msg).encode()

        self.socket.send_string(topic, flags=zmq.SNDMORE)
        self.socket.send(m)


class CredentialProvider:
    def __init__(self, wallet: Wallet, ctx: zmq.Context, linger=500):
        self.ctx = ctx
        self.joined = []
        self.wallet = wallet
        self.linger = linger

    def callback(self, domain, key):
        # Try to connect to the publisher socket.
        socket = self.ctx.socket(zmq.SUB)

        socket.setsockopt(zmq.LINGER, self.linger)
        socket.setsockopt(zmq.TCP_KEEPALIVE, 1)

        socket.curve_secretkey = self.wallet.curve_sk
        socket.curve_publickey = self.wallet.curve_vk

        socket.curve_serverkey = key

        try:
            socket.connect(domain)

            self.joined.append((socket, domain, key))
            return True
        except zmq.error.Again:
            socket.close()
            return False


class Network:
    def __init__(self, wallet: Wallet, ctx: zmq.Context, socket_id):
        self.wallet = wallet
        self.ctx = ctx
        self.socket_id = socket_id

        self.provider = CredentialProvider(wallet=self.wallet, ctx=self.ctx)
        self.publisher = Publisher(socket_id=self.socket_id, wallet=self.wallet, ctx=self.ctx)

        self.authenticator = AsyncioAuthenticator(context=self.ctx)

        self.peers = {}
        self.subscriptions = []

        self.running = False

    def start(self):
        self.running = True
        self.authenticator.start()
        asyncio.ensure_future(self.update_peers())
        asyncio.ensure_future(self.check_subscriptions())

    async def update_peers(self):
        while self.running:
            while len(self.provider.joined) > 0:
                socket, domain, key = self.provider.joined.pop(0)

                self.peers[key] = socket

                self.publisher.publish(topic=b'join', msg={'domain': domain, 'key': key})

    async def check_subscriptions(self):
        while self.running:
            for socket in self.peers.values():
                try:
                    event = await socket.poll(timeout=50, flags=zmq.POLLIN)
                    if event:
                        msg = await socket.recv_multipart()
                        self.subscriptions.append(msg)

                except zmq.error.ZMQError:
                    socket.close() # broadcast error or try to handle it?

    async def process_subscriptions(self):
        while self.running:
            while len(self.subscriptions) > 0:
                topic, msg = self.subscriptions.pop(0)
