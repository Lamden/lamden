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

from lamden.sockets.publisher import Publisher
from lamden.sockets.router import Router

WORK_SERVICE = 'work'


class Processor:
    async def process_message(self, msg):
        raise NotImplementedError


class QueueProcessor(Processor):
    def __init__(self):
        self.q = []

    async def process_message(self, msg):
        self.q.append(msg)


# class CredentialProvider:
#     def __init__(self, wallet: Wallet, ctx: zmq.Context, linger=500):
#         self.ctx = ctx
#         self.joined = []
#         self.wallet = wallet
#         self.linger = linger

#     def callback(self, domain, key):
#         # self.log.debug(f"Connection from {key} {domain}")
#         # Try to connect to the publisher socket.
#         socket = self.ctx.socket(zmq.SUB)

#         socket.setsockopt(zmq.LINGER, self.linger)
#         socket.setsockopt(zmq.TCP_KEEPALIVE, 1)

#         socket.curve_secretkey = self.wallet.curve_sk
#         socket.curve_publickey = self.wallet.curve_vk

#         socket.curve_serverkey = z85_key(key)

#         try:
#             socket.connect(domain)
#             socket.subscribe(b'')

#             self.joined.append((socket, domain, key))
#             self.log.debug(f"Connected to {key} {domain}")
#             return True
#         except zmq.error.Again:
#             socket.close()
#             return False


class Network:
    def __init__(self, wallet: Wallet, socket_id, max_peer_strikes, testing=False,
                 debug=False, boot_nodes={}):
        self.testing = testing
        self.debug = debug
        self.wallet = wallet
        self.max_peer_strikes = max_peer_strikes     
        self.socket_id = socket_id
        self.router_address = socket_id.replace(':180', ':190')
        self.ctx = zmq.asyncio.Context()
        self.boot_nodes = boot_nodes

        self.log = get_logger("NEW_SOCKETS")
        self.hello_response = ('{"response":"pub_info", "address": "%s", "topics": [""]}' % self.socket_id).encode()

        # self.provider = CredentialProvider(wallet=self.wallet, ctx=self.ctx)  # zap
        self.publisher = Publisher(
            testing=self.testing,
            debug=self.debug,
            socket_id=self.socket_id,
            ctx=self.ctx
        )

        self.router = Router(address=self.router_address, router_wallet=self.wallet,
                             public_keys=self.boot_nodes, callback=self.router_callback)

        boot_node_vks = list(boot_nodes.keys())
        boot_node_keys = []
        for vk in boot_node_vks:
            boot_node_keys.append(z85_key(vk))

        self.peers = {}
        self.peer_blacklist = []
        self.subscriptions = []
        self.services = {}

        self.running = False

    async def start(self):
        self.running = True
        self.publisher.setup_socket()
        self.router.start()

    def stop(self):
        print('network.stop()')
        self.running = False
        self.publisher.stop()
        self.router.stop()
        for peer in self.peers:
            self.peers[peer].stop()
        self.ctx.term()

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

    async def connect(self, ip, key):
        if key in self.peer_blacklist:
            # TODO how does a blacklisted peer get back in good standing?
            self.log.error(f'Attempted connection from blacklisted peer {key[:8]}!!')
            return False

        # Add the node to authorized list of the router in case it was not part of the boot nodes
        # self.router.cred_provider.add_key(z85_key(key))

        self.log.debug(f"Connecting to {key} {ip}")

        try:
            self.add_peer(ip=ip, key=key)
            return True
        except zmq.error.Again as error:
            self.log.error(error)
            # socket.close()
            return False

    def router_callback(self, ident: str, msg: str):
        if msg == b'hello':
            print('Router sending pub_info response to %s' % ident)
            self.router.send_msg(ident, self.hello_response)

    def add_peer(self, ip, key):
        self.peers[key] = Peer(
            testing=self.testing,
            debug=self.debug,
            ctx=self.ctx,
            ip=ip,
            key=z85_key(key),
            blacklist=lambda x: self.blacklist_peer(key=x),
            services=self.get_services,
            max_strikes=self.max_peer_strikes,
            wallet=self.wallet
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

    return z85.encode(pk)