import json
import requests
import zmq
from lamden.nodes.filequeue import FileQueue, STORAGE_HOME
from lamden.peer import Peer
from lamden.crypto.wallet import Wallet
from lamden.crypto.z85 import z85_key
from urllib.parse import urlparse

from lamden.logger.base import get_logger

from zmq.utils import z85
import zmq.asyncio
import asyncio
from nacl.bindings import crypto_sign_ed25519_pk_to_curve25519

from contracting.db.encoder import encode, decode
from contracting.db.driver import ContractDriver

from lamden.sockets.publisher import Publisher
from lamden.sockets.router import Router

WORK_SERVICE = 'work'
LATEST_BLOCK_INFO = 'latest_block_info'
GET_LATEST_BLOCK = 'get_latest_block'
GET_BLOCK = "get_block"
GET_CONSTITUTION = "get_constitution"
GET_ALL_PEERS = "get_all_peers"
GET_NETWORK = 'get_node_list'


class Processor:
    async def process_message(self, msg):
        raise NotImplementedError


class QueueProcessor(Processor):
    def __init__(self):
        self.q = []

    async def process_message(self, msg):
        self.q.append(msg)


class NewPeerProcessor(Processor):
    def __init__(self, callback):
        self.new_peer_callback = callback

    async def process_message(self, msg):
        self.new_peer_callback(msg=msg)


class Network:
    def __init__(self, wallet: Wallet, socket_base, driver: ContractDriver=ContractDriver(), socket_ports=None, testing=False, debug=False):
        self.testing = testing
        self.debug = debug
        self.wallet = wallet

        self.driver = driver

        self.socket_base = socket_base
        if socket_ports:
            self.socket_ports = socket_ports
        else:
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

        self.router = Router(
            get_all_peers=self.get_peer_list,
            router_wallet=self.wallet,
            callback=self.router_callback,
            logger=self.log
        )

        self.peers = {}
        self.peer_blacklist = []
        self.subscriptions = []
        self.services = {}
        self.actions = {}

        self.ip = requests.get('http://api.ipify.org').text

        self.running = False

        new_peer_processor = NewPeerProcessor(callback=self.process_new_peer_connection)
        self.add_service("new_peer_connection", new_peer_processor)

    @property
    def publisher_address(self):
        return '{}:{}'.format('tcp://*', self.socket_ports.get('publisher'))

    @property
    def router_address(self):
        return '{}:{}'.format('tcp://*', self.socket_ports.get('router'))

    @property
    def external_address(self):
        return '{}{}:{}'.format('tcp://', self.ip, self.socket_ports.get('router'))

    @property
    def hello_response(self):
        latest_block_info = self.get_latest_block_info()
        block_num = latest_block_info.get('number')
        hlc_timestamp = latest_block_info.get("hlc_timestamp")
        return ('{"response":"pub_info", "topics": [""], "latest_block_num": %d, "latest_hlc_timestamp": "%s"}' % (block_num, hlc_timestamp)).encode()

    @property
    def log(self):
        return get_logger(self.router_address)

    @property
    def vk(self):
        return self.wallet.verifying_key

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

        try:
            self.router.join()
        except RuntimeError:
            pass

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

    def add_action(self, name: str, processor: Processor):
        self.actions[name] = processor

    def get_actions(self):
        return self.actions

    def get_all_peers(self):
        return self.actions[GET_ALL_PEERS]()

    def get_peer(self, vk):
        return self.peers.get(vk, None)

    def get_peer_by_ip(self, ip):
        for vk, peer in self.peers.items():
            ip = peer.get('ip')
            if ip == peer.get('ip'):
                return peer

        return None

    def get_latest_block_info(self):
        latest_block = self.actions[GET_LATEST_BLOCK]()
        if not latest_block:
            latest_block = {}
        return {
                'number': latest_block.get('number', 0),
                'hlc_timestamp': latest_block.get('hlc_timestamp', '0'),
            }

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
                socket, domain, vk = self.provider.joined.pop(0)

                if self.peers.get(vk) is None:
                    self.add_peer(socket=socket, domain=domain, vk=vk)
                    await self.publisher.publish(topic=b'join', msg={'domain': domain, 'key': vk})

    def connect(self, ip, vk):
        if vk == self.vk:
            print(f'[{self.external_address}][NETWORK] Attempted connection to self "{vk}"')
            self.log.warning(f'[NETWORK] Attempted connection to self "{vk}"')
            return

        if vk in self.peer_blacklist:
            # TODO how does a blacklisted peer get back in good standing?
            self.log.error(f'Attempted connection from blacklisted peer {vk[:8]}!!')
            return False

        # Add the node to authorized list of the router in case it was not part of the boot nodes
        # self.router.cred_provider.add_key(z85_key(key))

        self.log.debug(f"Connecting to {vk} {ip}")

        try:
            peer = self.get_peer(vk=vk)
            if peer:
                if peer.running:
                    # If we are already connected to this peer then do nothing
                    print(f'[{self.external_address}][NETWORK] Already connected to "{vk}" at {ip}')
                    return
                else:
                    print(f'[{self.external_address}][NETWORK] Attempting to reconnect to "{vk}" at {ip}')
                    # if we are not connected then update the ip and try to connect
                    peer.set_ip(address=ip)
                    peer.start()
            else:
                print(f'[{self.external_address}][NETWORK] Adding Peer "{vk}" at {ip}')
                self.add_peer(ip=ip, vk=vk)
            return True
        except zmq.error.Again as error:
            self.log.error(error)
            # socket.close()
            return False

    def router_callback(self, router: Router, ident: str, msg: str):
        try:
            # msg = str(msg, 'utf-8')
            msg = json.loads(msg)
            action = msg.get('action')
        except Exception as err:
            print(err)
            self.log.error(err)
            return

        if action == 'ping':
            self.router.send_msg(ident, '{"response": "ping"}'.encode())

        if action == 'hello':
            self.router.send_msg(ident, self.hello_response)

            # print('Router sending pub_info response to %s' % ident)
            peer = self.get_peer(ident)
            vk = json.loads(ident)
            ip = msg.get('ip')

            '''
            if not peer:
                self.connect(vk=vk, ip=ip)
            else:
                if not peer.running:
                    self.connect(vk=vk, ip=ip)
            '''

        if action == LATEST_BLOCK_INFO:
            latest_block_info = self.get_latest_block_info()
            block_num = latest_block_info.get('number')
            hlc_timestamp = latest_block_info.get("hlc_timestamp")
            msg = ('{"response": "%s", "number": %d, "hlc_timestamp": "%s"}' % (LATEST_BLOCK_INFO, block_num, hlc_timestamp)).encode()
            self.router.send_msg(ident, msg)

        if action == GET_BLOCK:
            block_num = msg.get('block_num', None)
            hlc_timestamp = msg.get('hlc_timestamp', None)
            if block_num or hlc_timestamp:
                block_info = self.actions[GET_BLOCK](v=block_num or hlc_timestamp)
                block_info = encode(block_info)
                self.router.send_msg(
                    ident,
                    ('{"response": "%s", "block_info": %s}' % (GET_BLOCK, block_info)).encode()
                )

        if action == GET_NETWORK:
            node_list = []
            constitution = self.actions[GET_CONSTITUTION]()

            for vk in constitution.get('masternodes'):
                peer = self.peers.get(vk, None)
                if not peer:
                    if vk == self.wallet.verifying_key:
                        ip = f'tcp://{self.ip}:{self.socket_ports.get("router")}'
                    else:
                        continue
                else:
                    ip = peer.dealer_address
                node_list.append({'vk': vk, 'ip': ip, 'node_type': 'masternode'})

            for vk in constitution.get('delegates'):
                peer = self.peers.get(vk, None)
                if not peer:
                    if vk == self.wallet.verifying_key:
                        ip = f'tcp://{self.ip}:{self.socket_ports.get("router")}'
                    else:
                        continue
                else:
                    ip = peer.dealer_address

                node_list.append({'vk': vk, 'ip': ip, 'node_type': 'delegate'})

            node_list = json.dumps(node_list)
            msg = ('{"response": "%s", "node_list": %s}' % (GET_NETWORK, node_list)).encode()
            self.router.send_msg(ident, msg)

    def add_peer(self, ip, vk):
        self.peers[vk] = Peer(
            testing=self.testing,
            debug=self.debug,
            ctx=self.ctx,
            get_network_ip=lambda: self.external_address,
            ip=ip,
            server_key=z85_key(vk),
            vk=vk,
            blacklist=lambda x: self.blacklist_peer(key=x),
            services=self.get_services,
            wallet=self.wallet,
            logger=self.log,
            connected_callback=self.peer_connected
        )
        self.peers[vk].start()

    def peer_connected(self, vk):
        peer = self.get_peer(vk=vk)
        self.publisher.announce_new_peer_connection(vk=vk, ip=peer.dealer_address)

    def process_new_peer_connection(self, msg):
        print(f'[{self.external_address}][NEW PEER CONNECTED] {msg}')
        vk = msg.get('vk')
        ip = msg.get('ip')

        self.connect(ip=ip, vk=vk)

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
                    self.log.info(f'Waiting to connect to {peer.dealer_address}...')

            self.log.info(f'Connected to {num_of_peers_connected}/{num_of_peers} peers.')

    def get_peers_for_consensus(self):
        allPeers = {}
        peers_from_blockchain = self.get_all_peers(not_me=True)
        # print({'peers_from_blockchain': peers_from_blockchain})

        for key in peers_from_blockchain:
            # print(key)
            # print({'network_peers': self.network.peers})
            if self.peers[key].currently_participating():
                allPeers[key] = peers_from_blockchain[key]

        return allPeers

    def get_all_peers(self, not_me=False):
        return {
            ** self.get_delegate_peers(not_me),
            ** self.get_masternode_peers(not_me)
        }

    def _get_member_peers(self, contract_name):
        ''' GET FROM DB INSTEAD
        members = self.client.get_var(
            contract=contract_name,
            variable='S',
            arguments=['members']
        )
        '''

        members = self.driver.driver.get(f'{contract_name}.S:members')

        member_peers = dict()

        for vk in members:
            if vk == self.wallet.verifying_key:
                member_peers[vk] = self.ip
            else:
                peer = self.peers.get(vk, None)
                if peer is not None:
                    if peer.ip is not None:
                        member_peers[vk] = peer.ip

        return member_peers

    def get_delegate_peers(self, not_me=False):
        peers = self._get_member_peers('delegates')
        # print({'delegate': peers})
        if not_me and self.wallet.verifying_key in peers:
            del peers[self.wallet.verifying_key]
        return peers

    def get_masternode_peers(self, not_me=False):
        peers = self._get_member_peers('masternodes')
        # print({'masternode': peers})
        if not_me and self.wallet.verifying_key in peers:
            del peers[self.wallet.verifying_key]

        return peers

    def get_peer_list(self):
        delegates = self.driver.driver.get(f'delegates.S:members') or []
        masternodes = self.driver.driver.get(f'masternodes.S:members') or []
        all_nodes = masternodes + delegates
        return all_nodes

    def set_peers_not_in_consensus(self, keys):
        for key in keys:
            try:
                self.peers[key].not_in_consensus()
                self.log.info(f'DROPPED {key[:8]} FROM CONSENSUS!')
            except KeyError:
                self.log.error(f'Cannot drop {key[:8]} from consensus because they are not a peer!')

    def peer_add_strike(self, key):
        self.peers[key].add_strike()


class MessageProcessor:
    def __init__(self):
        self.queues = {}
        self.services = {}
        self.is_running = False

    def add_service(self, name: str, processor: Processor):
        self.services[name] = processor
        self.queues[name] = FileQueue(root=STORAGE_HOME.joinpath(name))

    def check_inbox(self):
        for k, v in self.queues.items():
            try:
                item = v.pop(0)
                self.services[k].process_message(item)
            except IndexError:
                pass

    async def loop(self):
        self.is_running = True

        while self.is_running:
            self.check_inbox()
            await asyncio.sleep(0)