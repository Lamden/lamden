import zmq
import json
import time
from lamden.peer import Peer
from lamden.crypto.wallet import Wallet
from zmq.auth.asyncio import AsyncioAuthenticator
from lamden.logger.base import get_logger

from zmq.utils import z85
import zmq.asyncio
import asyncio
from nacl.bindings import crypto_sign_ed25519_pk_to_curve25519

from contracting.db.encoder import encode, decode

WORK_SERVICE = 'work'


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

        self.log = get_logger("PUBLISHER")

    def setup_socket(self):
        self.socket = self.ctx.socket(zmq.PUB)

        # self.socket.curve_secretkey = self.wallet.curve_sk
        # self.socket.curve_publickey = self.wallet.curve_vk

        # self.socket.curve_server = True

        self.socket.bind(self.address)

    async def publish(self, topic, msg):
        if topic == WORK_SERVICE:
            self.log.debug(json.dumps({
                'type': 'tx_lifecycle',
                'file': 'new_sockets',
                'event': 'publish_new_tx',
                'hlc_timestamp': msg['hlc_timestamp'],
                'system_time': time.time()
            }))

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
        # self.log.debug(f"Connection from {key} {domain}")
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
    def __init__(self, wallet: Wallet, ctx: zmq.Context, socket_id, max_peer_strikes):
        self.wallet = wallet
        self.max_peer_strikes = max_peer_strikes
        self.ctx = ctx
        self.socket_id = socket_id

        self.log = get_logger("NEW_SOCKETS")

        # self.provider = CredentialProvider(wallet=self.wallet, ctx=self.ctx)  # zap
        self.publisher = Publisher(socket_id=self.socket_id, wallet=self.wallet, ctx=self.ctx)

        # self.authenticator = AsyncioAuthenticator(context=self.ctx)

        self.peers = {}
        self.peer_blacklist = []
        self.subscriptions = []
        self.services = {}

        self.running = False

    async def start(self):
        self.running = True
        # self.authenticator.start()
        self.publisher.setup_socket()
        # asyncio.ensure_future(self.update_peers())
        # asyncio.ensure_future(self.process_subscriptions())

    def stop(self):
        self.running = False
        self.publisher.stop()
        for peer in self.peers:
            self.peers[peer].stop()

    def disconnect_peer(self, key):
        self.peers[key].stop()

    def remove_peer(self, key):
        self.peers[key].pop()

    def add_service(self, name: str, processor: Processor):
        self.services[name] = processor

    def get_services(self):
        return self.services

    def add_message_to_subscriptions_queue(self, topic, msg):
        encoded_msg = encode(msg).encode()
        encoded_topic = bytes(topic, 'utf-8')
        asyncio.ensure_future(self.process_subscription((encoded_topic, encoded_msg)))
        # self.subscriptions.append((encoded_topic, encoded_msg))

    async def update_peers(self):
        while self.running:
            while len(self.provider.joined) > 0:
                socket, domain, key = self.provider.joined.pop(0)

                if self.peers.get(key) is None:
                    self.add_peer(socket=socket, domain=domain, key=key)
                    await self.publisher.publish(topic=b'join', msg={'domain': domain, 'key': key})

    def connect(self, socket, domain, key, wallet, linger=500):
        if key in self.peer_blacklist:
            # TODO how does a blacklisted peer get back in good standing?
            self.log.error(f'Attempted connection from blacklisted peer {key[:8]}!!')
            return False

        self.log.debug(f"Connecting to {key} {domain}")

        socket.setsockopt(zmq.LINGER, linger)
        socket.setsockopt(zmq.TCP_KEEPALIVE, 1)

        # socket.curve_secretkey = wallet.curve_sk
        # socket.curve_publickey = wallet.curve_vk

        # socket.curve_serverkey = z85_key(key)

        try:
            socket.connect(domain)
            socket.subscribe(b'')
            self.add_peer(socket=socket, domain=domain, key=key)
            return True
        except zmq.error.Again as error:
            self.log.error(error)
            socket.close()
            return False

    def add_peer(self, socket, domain, key):
        self.peers[key] = Peer(
            socket=socket,
            domain=domain,
            key=key,
            blacklist=lambda x: self.blacklist_peer(key=x),
            services=self.get_services,
            max_strikes=self.max_peer_strikes
        )
        self.peers[key].start()

    def blacklist_peer(self, key):
        self.disconnect_peer(key)
        self.peer_blacklist.append(key)


def z85_key(key):
    bvk = bytes.fromhex(key)
    try:
        pk = crypto_sign_ed25519_pk_to_curve25519(bvk)
    # Error is thrown if the VK is not within the possibility space of the ED25519 algorithm
    except RuntimeError:
        return

    return z85.encode(pk).decode('utf-8')



