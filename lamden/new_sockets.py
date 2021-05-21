import zmq
import json
from lamden.crypto.wallet import Wallet
from zmq.auth.asyncio import AsyncioAuthenticator
from lamden.logger.base import get_logger

from zmq.utils import z85
import zmq.asyncio
import asyncio
from nacl.bindings import crypto_sign_ed25519_pk_to_curve25519

from contracting.db.encoder import encode, decode


class Processor:
    async def process_message(self, msg):
        raise NotImplementedError


class QueueProcessor(Processor):
    def __init__(self):
        self.q = []

    async def process_message(self, msg):
        self.q.append(msg)


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

        # self.socket.curve_secretkey = self.wallet.curve_sk
        # self.socket.curve_publickey = self.wallet.curve_vk

        # self.socket.curve_server = True

        self.socket.bind(self.address)

    async def publish(self, topic, msg):
        # m = json.dumps(msg).encode()
        m = encode(msg).encode()

        await self.socket.send_string(topic, flags=zmq.SNDMORE)
        await self.socket.send(m)

    def stop(self):
        self.socket.close()


class CredentialProvider:
    def __init__(self, wallet: Wallet, ctx: zmq.Context, linger=500):
        self.ctx = ctx
        self.joined = []
        self.wallet = wallet
        self.linger = linger

    def callback(self, domain, key):
        self.log.debug(f"Connection from {key} {domain}")
        # Try to connect to the publisher socket.
        socket = self.ctx.socket(zmq.SUB)

        socket.setsockopt(zmq.LINGER, self.linger)
        socket.setsockopt(zmq.TCP_KEEPALIVE, 1)

        socket.curve_secretkey = self.wallet.curve_sk
        socket.curve_publickey = self.wallet.curve_vk

        socket.curve_serverkey = z85_key(key)

        try:
            socket.connect(domain)
            socket.subscribe(b'')

            self.joined.append((socket, domain, key))
            self.log.debug(f"Connected to {key} {domain}")
            return True
        except zmq.error.Again:
            socket.close()
            return False


class Network:
    def __init__(self, wallet: Wallet, ctx: zmq.Context, socket_id):
        self.wallet = wallet
        self.ctx = ctx
        self.socket_id = socket_id

        self.log = get_logger("NEW_SOCKETS")

        # self.provider = CredentialProvider(wallet=self.wallet, ctx=self.ctx)  # zap
        self.publisher = Publisher(socket_id=self.socket_id, wallet=self.wallet, ctx=self.ctx)

        # self.authenticator = AsyncioAuthenticator(context=self.ctx)

        self.peers = {}
        self.subscriptions = []
        self.services = {}

        self.running = False

    async def start(self):
        self.running = True
        # self.authenticator.start()
        self.publisher.setup_socket()
        #asyncio.ensure_future(self.update_peers())
        asyncio.ensure_future(self.process_subscriptions())

    def stop(self):
        self.running = False
        self.publisher.stop()
        for key, value in self.peers.items():
            domain, socket = value
            socket.close()

    def add_service(self, name: str, processor: Processor):
        self.services[name] = processor

    def add_message_to_subscriptions_queue(self, topic, msg):
        encoded_msg =  encode(msg).encode()
        encoded_topic = bytes(topic, 'utf-8')
        self.subscriptions.append((encoded_topic, encoded_msg))

    async def update_peers(self):
        while self.running:
            while len(self.provider.joined) > 0:
                socket, domain, key = self.provider.joined.pop(0)

                if self.peers.get(key) is None:
                    self.peers[key] = (domain, socket)
                    await self.publisher.publish(topic=b'join', msg={'domain': domain, 'key': key})

    async def check_subscriptions(self):
        while self.running:
            for key, value in self.peers.items():
                domain, socket = value
                try:
                    event = await socket.poll(timeout=50, flags=zmq.POLLIN)
                    # self.log.info("got event!")
                    if event:
                        msg = await socket.recv_multipart()
                        self.subscriptions.append(msg)

                except zmq.error.ZMQError as error:
                    self.log.error(error)
                    socket.close()
                    # await self.publisher.publish(topic=b'leave', msg={'domain': domain, 'key': key})
            await asyncio.sleep(0)

    async def check_subscription(self, socket, key):
        while self.running:
            try:
                event = await socket.poll(timeout=50, flags=zmq.POLLIN)
                # self.log.info("got event!")
                if event:
                    data = await socket.recv_multipart()
                    await self.process_subscription(data)

            except zmq.error.ZMQError as error:
                self.log.error(error)
                socket.close()
                self.peers.pop(key)
                # await self.publisher.publish(topic=b'leave', msg={'domain': domain, 'key': key})

            await asyncio.sleep(0)

    async def process_subscription(self, data):
        topic, msg = data
        processor = self.services.get(topic.decode("utf-8"))
        message = json.loads(msg)
        if not message:
            self.log.error(msg)
            self.log.error(message)
        if processor is not None and message is not None:
            await processor.process_message(message)
            #self.log.info(f'Processed a subscription message {len(self.subscriptions)} left!')

    async def process_subscriptions(self):
        while self.running:
            if len(self.subscriptions) > 0:
                topic, msg = self.subscriptions.pop(0)
                processor = self.services.get(topic.decode("utf-8"))
                message = json.loads(msg)
                if not message:
                    self.log.error(msg)
                    self.log.error(message)
                if processor is not None and message is not None:
                    await processor.process_message(message)
                    self.log.info(f'Processed a subscription message {len(self.subscriptions)} left!')
            await asyncio.sleep(0)

    def connect(self, socket, domain, key, wallet, linger=500):
        self.log.debug(f"Connecting to {key} {domain}")

        socket.setsockopt(zmq.LINGER, linger)
        socket.setsockopt(zmq.TCP_KEEPALIVE, 1)

        # socket.curve_secretkey = wallet.curve_sk
        # socket.curve_publickey = wallet.curve_vk

        # socket.curve_serverkey = z85_key(key)

        try:
            socket.connect(domain)
            socket.subscribe(b'')
            self.peers[key] = (domain, socket)
            asyncio.ensure_future(self.check_subscription(socket, key))
            return True
        except zmq.error.Again as error:
            self.log.error(error)
            socket.close()
            return False


def z85_key(key):
    bvk = bytes.fromhex(key)
    try:
        pk = crypto_sign_ed25519_pk_to_curve25519(bvk)
    # Error is thrown if the VK is not within the possibility space of the ED25519 algorithm
    except RuntimeError:
        return

    return z85.encode(pk).decode('utf-8')
