import json
import requests

import zmq
import zmq.asyncio
import asyncio
import uvloop

from lamden.peer import Peer
from lamden.crypto.wallet import Wallet
from lamden.crypto.z85 import z85_key

from lamden.logger.base import get_logger

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

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

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
    def __init__(self, wallet: Wallet = Wallet(), driver: ContractDriver = ContractDriver(), socket_ports: dict = None):
        self.wallet = wallet
        self.driver = driver

        self.socket_ports = dict(socket_ports) or dict({
            'router': 19000,
            'publisher': 19080,
            'webserver': 18080
        })

        self.peers = {}
        self.subscriptions = []
        self.services = {}
        self.actions = {}

        self.external_ip = requests.get('http://api.ipify.org').text

        self.running = False

        new_peer_processor = NewPeerProcessor(callback=self.process_new_peer_connection)
        self.add_service("new_peer_connection", new_peer_processor)

        self.ctx = zmq.asyncio.Context().instance()

        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        self.setup_publisher()
        self.setup_router()

    @property
    def is_running(self):
        return self.running

    @property
    def publisher_address(self):
        return '{}:{}'.format('tcp://*', self.socket_ports.get('publisher'))

    @property
    def router_address(self):
        return '{}:{}'.format('tcp://*', self.socket_ports.get('router'))

    @property
    def external_address(self):
        return '{}{}:{}'.format('tcp://', self.external_ip, self.socket_ports.get('router'))

    @property
    def hello_response(self):
        latest_block_info = self.get_latest_block_info()
        block_num = latest_block_info.get('number')
        hlc_timestamp = latest_block_info.get("hlc_timestamp")
        return ('{"response":"hello", "topics": [""], "latest_block_num": %d, "latest_hlc_timestamp": "%s"}' % (block_num, hlc_timestamp)).encode()

    @property
    def vk(self):
        return self.wallet.verifying_key

    @property
    def peer_list(self):
        return self.peers.values()

    def log(self, log_type: str, message: str) -> None:
        named_message = f'[NETWORK]{message}'

        logger = get_logger(f'{self.router_address}')
        if log_type == 'info':
            logger.info(named_message)
        if log_type == 'error':
            logger.error(named_message)
        if log_type == 'warning':
            logger.warning(named_message)

        print(f'[{self.router_address}]{named_message}')

    def setup_publisher(self):
        self.publisher = Publisher()
        self.publisher.set_address(port=self.socket_ports.get('publisher'))

    def setup_router(self):
        self.router = Router(
            wallet=self.wallet,
            message_callback=self.router_callback
        )
        self.router.set_address(port=self.socket_ports.get('router'))

    def start(self) -> None:
        self.log('info', f'Publisher Address {self.publisher_address}')
        self.log('info', f'Router Address {self.router_address}')

        self.publisher.start()
        self.router.run_curve_server()

        self.loop.run_until_complete(self.starting())

        self.running = True

        self.log('info', 'Started.')

    async def starting(self):
        while not self.publisher.is_running or not self.router.is_running:
            await asyncio.sleep(0.1)

    def disconnect_peer(self, peer_vk):
        self.peers[peer_vk].stop()

    def remove_peer(self, peer_vk):
        self.peers[peer_vk].pop()

    def add_service(self, name: str, processor: Processor):
        self.services[name] = processor

    def get_services(self):
        return self.services

    def add_action(self, name: str, processor: Processor):
        self.actions[name] = processor

    def get_actions(self):
        return self.actions

    def num_of_peers(self):
        return len(self.peer_list)

    def num_of_peers_connected(self):
        return len(list(filter(lambda x: x is True, [peer.is_running for peer in self.peer_list])))

    def all_peers_connected(self):
        return self.num_of_peers() == self.num_of_peers_connected()

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

    def connect_peer(self, ip: str, vk: str) -> bool:
        if vk == self.vk:
            self.log('warning', f'Attempted connection to self "{vk}"')
            return

        self.log('info', f"Connecting to {vk} {ip}")

        try:
            peer = self.get_peer(vk=vk)
            if peer:
                if peer.is_running:
                    # If we are already connected to this peer then do nothing
                    self.log('info', f'Already connected to "{vk}" at {ip}')
                    return

            else:
                self.log('info', f'Adding Peer "{vk}" at {ip}')
                self.add_peer(ip=ip, vk=vk)
                self.start_peer(vk=vk)
            return True
        except zmq.error.Again as error:
            self.log('error', error)
            return False

    def router_callback(self, ident: str, msg: str) -> None:
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

            # print('Router sending hello response to %s' % ident)
            vk = json.loads(ident)
            ip = msg.get('ip')

            peer = self.get_peer(vk=vk)

            if not peer:
                self.connect(vk=vk, ip=ip)

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
                        ip = f'tcp://{self.external_ip}:{self.socket_ports.get("router")}'
                    else:
                        continue
                else:
                    ip = peer.dealer_address
                node_list.append({'vk': vk, 'ip': ip, 'node_type': 'masternode'})

            for vk in constitution.get('delegates'):
                peer = self.peers.get(vk, None)
                if not peer:
                    if vk == self.wallet.verifying_key:
                        ip = f'tcp://{self.external_ip}:{self.socket_ports.get("router")}'
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
            get_network_ip=lambda: self.external_address,
            ip=ip,
            server_vk=vk,
            services=self.get_services,
            local_wallet=self.wallet
        )

    def start_peer(self, vk: str) -> None:
        self.peers[vk].start()

    def peer_connected(self, vk):
        peer = self.get_peer(vk=vk)
        self.publisher.announce_new_peer_connection(vk=vk, ip=peer.dealer_address)

    def process_new_peer_connection(self, msg):
        vk = msg.get('vk')

        if vk != self.vk:
            print(f'[{self.external_address}][NEW PEER CONNECTED] {msg}')
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
                member_peers[vk] = self.external_ip
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

    def stop(self):
        self.running = False

        for peer in self.peers:
            peer.stop()

        self.publisher.stop()
        self.router.stop()

        self.log('info', 'Stopped.')