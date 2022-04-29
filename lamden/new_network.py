import json
import requests
import zmq
import zmq.asyncio
import asyncio
import uvloop

from lamden.peer import Peer
from lamden.crypto.wallet import Wallet

from lamden.logger.base import get_logger

from contracting.db.encoder import encode
from contracting.db.driver import ContractDriver

from lamden.sockets.publisher import Publisher
from lamden.sockets.router import Router

WORK_SERVICE = 'work'
LATEST_BLOCK_INFO = 'latest_block_info'

ACTION_PING = "ping"
ACTION_HELLO = "hello"
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
    def __init__(self, wallet: Wallet = Wallet(), driver: ContractDriver = ContractDriver(), socket_ports: dict = None,
                 local: bool = False):

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

        self.local = local
        if self.local:
            self.external_ip = '127.0.0.1'
        else:
            self.external_ip = requests.get('http://api.ipify.org').text
        self.running = False

        self.add_service("new_peer_connection", NewPeerProcessor(callback=self.new_peer_connection_service))

        self.ctx = zmq.asyncio.Context()

        self.loop = None
        self.setup_event_loop()

        self.setup_publisher()
        self.setup_router()

    @property
    def is_running(self):
        return self.running
    @property
    def all_sockets_stopped(self):
        try:
            self_not_running = not self.is_running
            router_not_running = not self.router.is_running
            publisher_not_running = not self.publisher.is_running
            all_stopped = self_not_running and router_not_running and publisher_not_running
            return all_stopped
        except:
            return False

    @property
    def publisher_address(self):
        if self.local:
            return '{}:{}'.format('tcp://127.0.0.1', self.socket_ports.get('publisher'))
        else:
            return '{}:{}'.format('tcp://*', self.socket_ports.get('publisher'))

    @property
    def router_address(self):
        return '{}:{}'.format('tcp://*', self.socket_ports.get('router'))

    @property
    def external_address(self):
        return '{}{}:{}'.format('tcp://', self.external_ip, self.socket_ports.get('router'))

    @property
    def local_address(self):
        return '{}:{}'.format('tcp://127.0.0.1', self.socket_ports.get('router'))

    @property
    def vk(self):
        return self.wallet.verifying_key

    @property
    def peer_list(self):
        return self.peers.values()

    def log(self, log_type: str, message: str) -> None:
        named_message = f'[NETWORK] {message}'

        logger = get_logger(f'{self.external_address}')
        if log_type == 'info':
            logger.info(named_message)
        if log_type == 'error':
            logger.error(named_message)
        if log_type == 'warning':
            logger.warning(named_message)

        print(f'[{self.external_address}]{named_message}\n')

    def setup_event_loop(self):
        try:
            self.loop = asyncio.get_event_loop()

            if self.loop.is_closed():
                self.loop = None

        except RuntimeError:
            pass

        if not self.loop:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    def setup_publisher(self):
        self.publisher = Publisher(
            ctx=self.ctx,
            network_ip=self.external_address
        )
        self.publisher.set_address(port=self.socket_ports.get('publisher'))

    def setup_router(self):
        self.router = Router(
            wallet=self.wallet,
            message_callback=self.router_callback,
            ctx=self.ctx,
            network_ip=self.external_address
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

    async def starting(self) -> None:
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

    def get_services(self) -> dict:
        return self.services

    def add_action(self, name: str, processor: Processor) -> None:
        self.actions[name] = processor

    def get_actions(self) -> dict:
        return self.actions

    def num_of_peers(self) -> int:
        return len(self.peer_list)

    def num_of_peers_connected(self) -> int:
        return len(list(filter(lambda x: x is True, [peer.is_connected for peer in self.peer_list])))

    def all_peers_connected(self):
        return self.num_of_peers() == self.num_of_peers_connected()

    def get_all_peers(self) -> list:
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

    def add_peer(self, ip: str, vk: str) -> None:
        self.peers[vk] = Peer(
            get_network_ip=lambda: self.external_address,
            ip=ip,
            server_vk=vk,
            services=self.get_services,
            local_wallet=self.wallet,
            socket_ports=self.socket_ports,
            connected_callback=self.connected_to_peer_callback,
            ctx=self.ctx,
            local=self.local
        )

    def start_peer(self, vk: str) -> None:
        self.peers[vk].start()

    def connect_peer(self, ip: str, vk: str) -> bool:
        if vk == self.vk:
            self.log('warning', f'Attempted connection to self "{vk}".')
            return

        # Get list of approved nodes from state
        node_vk_list_from_smartcontracts = self.get_masternode_and_delegate_vk_list()

        if vk not in node_vk_list_from_smartcontracts:
            self.log('warning', f'Attempted to add a node not in the smart contract. "{vk}"')
            return

        # Refesch credentials provider with approved nodes from state
        self.router.refresh_cred_provider_vks(vk_list=node_vk_list_from_smartcontracts)

        # Get a reference to this peer
        peer = self.get_peer(vk=vk)

        if peer:
            if peer.request_address != ip:
                # if the ip is different from the one we have then switch to it
                peer.update_ip(new_ip=ip)
            else:
                # check that our connection to this node is okay
                asyncio.ensure_future(peer.test_connection())

        else:
            # Add this peer to our peer group
            self.log('info', f'Adding New Peer "{vk}" at {ip}')
            self.add_peer(ip=ip, vk=vk)
            self.start_peer(vk=vk)

    def connected_to_peer_callback(self, peer_vk: str) -> bool:
        peer = self.get_peer(vk=peer_vk)

        if not peer:
            return

        print(f'[{self.external_address}][NEW PEER CONNECTED] "{peer.local_vk}" at {peer.request_address}')

        ip = peer.request_address

        self.publisher.announce_new_peer_connection(ip=ip, vk=peer_vk)


    def new_peer_connection_service(self, msg: dict) -> None:
        if not msg:
            return

        peer_vk = msg.get('vk')

        if peer_vk is None:
            return

        if peer_vk != self.vk:
            peer_ip = msg.get('ip')

            if peer_ip is None:
                return

            self.connect_peer(ip=peer_ip, vk=peer_vk)

    async def connected_to_all_peers(self):
        self.log('info', f'Establishing connection with {self.num_of_peers} peers...')

        while self.num_of_peers_connected() < self.num_of_peers():
            await asyncio.sleep(1)

        self.log('info', f'Connected to all {self.num_of_peers()} peers!')

    def make_constitution(self):
        return {
            'masternodes': self.map_vk_to_ip(self.get_masternode_vk_list()),
            'delegates': self.map_vk_to_ip(self.get_delegate_vk_list())
        }

    def make_node_list(self) -> list:
        constitution = self.make_constitution()
        node_list = []

        for vk, ip in constitution.get('masternodes').items():
            node_list.append({'vk': vk, 'ip': ip, 'node_type': 'masternode'})

        for vk, ip in constitution.get('delegates').items():
            node_list.append({'vk': vk, 'ip': ip, 'node_type': 'delegate'})
        print (node_list)
        return node_list

    def get_peers_for_consensus(self):
        all_peers = self.get_masternode_and_delegate_vk_list()
        all_peers.remove(self.vk)
        return all_peers

    def map_vk_to_ip(self, vk_list: list) -> dict:
        vk_to_ip_map = dict()

        for vk in vk_list:
            if vk == self.wallet.verifying_key:
                vk_to_ip_map[vk] = self.external_address
            else:
                peer = self.get_peer(vk=vk)
                if peer is not None:
                    if peer.ip is not None:
                        vk_to_ip_map[vk] = peer.request_address

        return vk_to_ip_map

    def get_delegate_vk_list(self) -> list:
        return self.driver.get(f'delegates.S:members') or []

    def get_masternode_vk_list(self) -> list:
        return self.driver.get(f'masternodes.S:members') or []

    def get_masternode_and_delegate_vk_list(self) -> list:
        return self.get_masternode_vk_list() + self.get_delegate_vk_list()

    def hello_response(self, challenge: str = None) -> str:
        latest_block_info = self.get_latest_block_info()
        block_num = latest_block_info.get('number')
        hlc_timestamp = latest_block_info.get("hlc_timestamp")

        try:
            challenge_response = self.wallet.sign(challenge)
        except:
            challenge_response = ""

        return '{"response":"%s", "challenge_response": "%s","latest_block_num": %d, "latest_hlc_timestamp": "%s"}' % (ACTION_HELLO, challenge_response, block_num, hlc_timestamp)

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
                msg_str=json.dumps({"response": "ping"})
            )

        if action == ACTION_HELLO:
            ip = msg.get('ip')
            challenge = msg.get('challenge')

            self.log('info', f'Hello received challenge "{challenge}" from Peer "{ident_vk_string}" at {ip}')

            self.router.send_msg(
                to_vk=ident_vk_string,
                msg_str=self.hello_response(challenge=challenge)
            )

            self.connect_peer(vk=ident_vk_string, ip=ip)

        if action == ACTION_GET_LATEST_BLOCK:
            latest_block_info = self.get_latest_block_info()
            block_num = latest_block_info.get('number')
            hlc_timestamp = latest_block_info.get("hlc_timestamp")

            resp_msg = ('{"response": "%s", "number": %d, "hlc_timestamp": "%s"}' % (ACTION_GET_LATEST_BLOCK, block_num, hlc_timestamp))
            self.router.send_msg(
                to_vk=ident_vk_string,
                msg_str=resp_msg
            )

        if action == ACTION_GET_BLOCK:
            block_num = msg.get('block_num', None)
            hlc_timestamp = msg.get('hlc_timestamp', None)
            if block_num or hlc_timestamp:
                block_info = self.actions[ACTION_GET_BLOCK](v=block_num or hlc_timestamp)
                block_info = encode(block_info)

                self.router.send_msg(
                    to_vk=ident_vk_string,
                    msg_str=('{"response": "%s", "block_info": %s}' % (ACTION_GET_BLOCK, block_info))
                )

        if action == ACTION_GET_NETWORK:
            node_list = json.dumps(self.make_node_list())

            resp_msg = ('{"response": "%s", "node_list": %s}' % (ACTION_GET_NETWORK, node_list))

            self.router.send_msg(
                to_vk=ident_vk_string,
                msg_str=resp_msg
            )

    async def stop(self):
        self.running = False
        tasks = []
        for peer in self.peers.values():
            task = asyncio.ensure_future(peer.stop())
            tasks.append(task)

        await asyncio.gather(*tasks)

        self.publisher.stop()
        await self.router.stop()

        self.log('info', 'Stopped.')