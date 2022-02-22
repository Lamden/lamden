import zmq
from lamden.peer import Peer
from lamden.crypto.wallet import Wallet

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

class Network:
    def __init__(self, wallet: Wallet, socket_base, max_peer_strikes, testing=False,
                 debug=False, boot_nodes={}):
        self.testing = testing
        self.debug = debug
        self.wallet = wallet

        self.max_peer_strikes = max_peer_strikes

        self.socket_base = socket_base
        self.socket_ports = {
            'router': 19000,
            'publisher': 19080,
            'webserver': 18080
        }
        self.ctx = zmq.asyncio.Context()

        self.publisher = Publisher(
            testing=self.testing,
            debug=self.debug,
            ctx=self.ctx,
            logger=self.log
        )

        boot_node_vks = list(boot_nodes.keys())
        boot_node_keys = []
        for vk in boot_node_vks:
            boot_node_keys.append(z85_key(vk))

        self.router = Router(
            router_wallet=self.wallet,
            public_keys=boot_node_keys,
            callback=self.router_callback,
            logger=self.log
        )

        self.peers = {}
        self.peer_blacklist = []
        self.subscriptions = []
        self.services = {}

        self.running = False

    @property
    def publisher_address(self):
        return '{}:{}'.format('tcp://*', self.socket_ports.get('publisher'))

    @property
    def router_address(self):
        return '{}:{}'.format('tcp://*', self.socket_ports.get('router'))

    @property
    def hello_response(self):
        return ('{"response":"pub_info", "address": "%s", "topics": [""]}' % self.router_address).encode()

    @property
    def log(self):
        return get_logger(self.router_address)

    async def start(self):
        self.running = True

        self.log.info(self.publisher_address)
        self.log.info(self.router_address)

        self.publisher.log = self.log
        self.router.log = self.log

        self.publisher.address = self.publisher_address
        self.router.address = self.router_address

        self.publisher.setup_socket()
        self.router.start()

    def stop(self):
        # print('network.stop()')
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

    def set_socket_port(self, service, port_num):
        self.socket_ports[service] = port_num

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

    def connect(self, ip, key):
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
            # print('Router sending pub_info response to %s' % ident)
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
            wallet=self.wallet,
            logger=self.log
        )
        self.peers[key].start()

    def blacklist_peer(self, key):
        self.disconnect_peer(key)
        self.peer_blacklist.append(key)

    async def connected_to_all_peers(self):
        num_of_peers = len(self.peers)
        num_of_peers_connected = 0
        self.log.info(f'Establishing connection with {num_of_peers} peers...')

        while num_of_peers_connected < num_of_peers:
            await asyncio.sleep(5)
            num_of_peers_connected = 0

            for vk in self.peers:
                peer = self.peers[vk]
                if peer.sub_running:
                    num_of_peers_connected += 1
                else:
                    self.log.info(f'Waiting to connect to {peer.ip}...')

            self.log.info(f'Connected to {num_of_peers_connected}/{num_of_peers} peers.')

def z85_key(key):
    bvk = bytes.fromhex(key)
    try:
        pk = crypto_sign_ed25519_pk_to_curve25519(bvk)
    # Error is thrown if the VK is not within the possibility space of the ED25519 algorithm
    except RuntimeError:
        return

    return z85.encode(pk)