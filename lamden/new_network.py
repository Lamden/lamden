import json
import requests
from typing import Callable
import zmq
import zmq.asyncio
import asyncio
import uvloop

from lamden.peer import Peer
from lamden.crypto.wallet import Wallet

from lamden.logger.base import get_logger

from contracting.db.encoder import encode, decode
from contracting.db.driver import ContractDriver

from lamden.sockets.publisher import Publisher
from lamden.sockets.router import Router

WORK_SERVICE = 'work'
LATEST_BLOCK_INFO = 'latest_block_info'

ACTION_PING = "ping"
ACTION_HELLO = "helo"
ACTION_GET_LATEST_BLOCK = 'get_latest_block'
ACTION_GET_BLOCK = "get_block"
ACTION_GET_NETWORK = "get_node_list"

GET_CONSTITUTION = "get_constitution"
GET_ALL_PEERS = "get_all_peers"

EXCEPTION_PORT_NUM_NOT_INT = "port_num must be type int."

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

        try:
            self.socket_ports = dict(socket_ports)
        except TypeError:
            self.socket_ports =  dict({
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
        return ('{"response":"%s", "latest_block_num": %d, "latest_hlc_timestamp": "%s"}' % (ACTION_HELLO, block_num, hlc_timestamp)).encode()

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

    def remove_peer(self, peer_vk: str) -> None:
        peer = self.get_peer(vk=peer_vk)
        if not peer:
            return
        peer.stop()
        self.peers.pop(peer_vk)

    def add_service(self, name: str, processor: Processor) -> None:
        self.services[name] = processor

    def get_services(self):
        return self.services

    def add_action(self, name: str, processor: Processor) -> None:
        self.actions[name] = processor

    def get_actions(self):
        return self.actions

    def num_of_peers(self) -> int:
        return len(self.peer_list)

    def num_of_peers_connected(self):
        return len(list(filter(lambda x: x is True, [peer.is_connected for peer in self.peer_list])))

    def all_peers_connected(self):
        return self.num_of_peers() == self.num_of_peers_connected()

    def get_all_peers(self):
        return self.actions[GET_ALL_PEERS]()

    def get_peer(self, vk: str) -> Peer:
        return self.peers.get(vk, None)

    def get_peer_by_ip(self, ip: str) -> Peer:
        for peer in self.peers.values():
            if ip == peer.ip:
                return peer
        return None

    def get_latest_block_info(self):
        latest_block = self.actions[ACTION_GET_LATEST_BLOCK]()
        if not latest_block:
            latest_block = {}
        return {
                'number': latest_block.get('number', 0),
                'hlc_timestamp': latest_block.get('hlc_timestamp', '0'),
            }

    def set_socket_port(self, service: str, port_num: int) -> None:
        if not isinstance(port_num, int):
            raise AttributeError(EXCEPTION_PORT_NUM_NOT_INT)

        self.socket_ports[service] = port_num

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

    def router_callback(self, ident_vk_string: str, msg: str) -> None:
        try:
            msg = json.loads(msg)
            action = msg.get('action')
        except Exception as err:
            self.log('error', err)
            return

        if action == ACTION_PING:
            self.router.send_msg(
                to_vk=ident_vk_string,
                msg='{"response": "ping"}'.encode()
            )

        if action == ACTION_HELLO:
            self.router.send_msg(
                to_vk=ident_vk_string,
                msg=self.hello_response
            )

            ip = msg.get('ip')

            peer = self.get_peer(vk=ident_vk_string)

            if not peer:
                self.connect_peer(vk=ident_vk_string, ip=ip)

        if action == ACTION_GET_LATEST_BLOCK:
            latest_block_info = self.get_latest_block_info()
            block_num = latest_block_info.get('number')
            hlc_timestamp = latest_block_info.get("hlc_timestamp")

            resp_msg = ('{"response": "%s", "number": %d, "hlc_timestamp": "%s"}' % (ACTION_GET_LATEST_BLOCK, block_num, hlc_timestamp)).encode()
            self.router.send_msg(
                to_vk=ident_vk_string,
                msg=resp_msg
            )

        if action == ACTION_GET_BLOCK:
            block_num = msg.get('block_num', None)
            hlc_timestamp = msg.get('hlc_timestamp', None)
            if block_num or hlc_timestamp:
                block_info = self.actions[ACTION_GET_BLOCK](v=block_num or hlc_timestamp)
                block_info = encode(block_info)

                self.router.send_msg(
                    to_vk=ident_vk_string,
                    msg=('{"response": "%s", "block_info": %s}' % (ACTION_GET_BLOCK, block_info)).encode()
                )

        if action == ACTION_GET_NETWORK:
            node_list = []
            constitution = self.make_constitution()

            for vk in constitution.get('masternodes'):
                peer = self.peers.get(vk, None)
                if not peer:
                    if vk == self.wallet.verifying_key:
                        ip = f'tcp://{self.external_ip}:{self.socket_ports.get("router")}'
                    else:
                        continue
                else:
                    ip = peer.request_address
                node_list.append({'vk': vk, 'ip': ip, 'node_type': 'masternode'})

            for vk in constitution.get('delegates'):
                peer = self.peers.get(vk, None)
                if not peer:
                    if vk == self.wallet.verifying_key:
                        ip = f'tcp://{self.external_ip}:{self.socket_ports.get("router")}'
                    else:
                        continue
                else:
                    ip = peer.request_address

                node_list.append({'vk': vk, 'ip': ip, 'node_type': 'delegate'})

            node_list = json.dumps(node_list)
            resp_msg = ('{"response": "%s", "node_list": %s}' % (ACTION_GET_NETWORK, node_list)).encode()
            self.router.send_msg(
                to_vk=ident_vk_string,
                msg=resp_msg
            )

    def add_peer(self, ip: str, vk: str) -> None:
        self.peers[vk] = Peer(
            get_network_ip=lambda: self.external_address,
            ip=ip,
            server_vk=vk,
            services=self.get_services,
            local_wallet=self.wallet,
            socket_ports=self.socket_ports
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

    async def connected_to_all_peers(self):
        self.log('info', f'Establishing connection with {self.num_of_peers} peers...')

        while self.num_of_peers_connected() < self.num_of_peers():
            await asyncio.sleep(1)

        self.log('info', f'Connected to all {self.num_of_peers()} peers!')

    def make_constitution(self):
        return {
            'masternodes': self.get_masternode_peers(),
            'delegates': self.get_delegate_peers()
        }

    def get_peers_for_consensus(self):
        allPeers = {}
        peers_from_blockchain = self.get_all_peers(not_me=True)

        for key in peers_from_blockchain:
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

        if not_me and self.wallet.verifying_key in peers:
            del peers[self.wallet.verifying_key]
        return peers

    def get_masternode_peers(self, not_me=False):
        peers = self._get_member_peers('masternodes')

        if not_me and self.wallet.verifying_key in peers:
            del peers[self.wallet.verifying_key]

        return peers

    def get_peer_list(self):
        delegates = self.driver.driver.get(f'delegates.S:members') or []
        masternodes = self.driver.driver.get(f'masternodes.S:members') or []
        all_nodes = masternodes + delegates
        return all_nodes

    def stop(self):
        self.running = False

        for peer in self.peers:
            peer.stop()

        self.publisher.stop()
        self.router.stop()

        self.log('info', 'Stopped.')