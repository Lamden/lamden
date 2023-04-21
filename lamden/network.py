import json
import requests
import zmq
import zmq.asyncio
import asyncio
import random
import uvloop
import socket
from typing import List

from lamden.utils import hlc
from lamden.peer import Peer, ACTION_HELLO, ACTION_PING, ACTION_GET_BLOCK, ACTION_GET_LATEST_BLOCK, ACTION_GET_NEXT_BLOCK, ACTION_GET_NETWORK_MAP

from lamden.crypto.wallet import Wallet
from lamden.storage import BlockStorage, get_latest_block_height

from lamden.logger.base import get_logger

from contracting.db.encoder import encode, decode
from contracting.db.driver import ContractDriver

from lamden.sockets.publisher import Publisher
from lamden.sockets.router import Router

WORK_SERVICE = 'work'
LATEST_BLOCK_INFO = 'latest_block_info'

GET_CONSTITUTION = "get_constitution"
GET_ALL_PEERS = "get_all_peers"

EXCEPTION_PORT_NUM_NOT_INT = "port_num must be type int."

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

class Processor:
    async def process_message(self, msg):
        raise NotImplementedError


class NewPeerProcessor(Processor):
    def __init__(self, callback):
        self.new_peer_callback = callback

    async def process_message(self, msg):
        self.new_peer_callback(msg=msg)

class PeerShutdownProcessor(Processor):
    def __init__(self, callback):
        self.shutdown_peer_callback = callback

    async def process_message(self, msg):
        self.shutdown_peer_callback(msg=msg)

class Network:
    def __init__(self, wallet: Wallet = Wallet(), driver: ContractDriver = ContractDriver(),
                 block_storage: BlockStorage = None, socket_ports: dict = None, local: bool = False):

        self.wallet = wallet
        self.driver = driver
        self.block_storage = block_storage if block_storage is not None else BlockStorage()

        self.local = local

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

        if self.local:
            self.external_ip = '127.0.0.1'
            self.share_ip = self.get_local_ip()
        else:
            #self.external_ip = requests.get('http://api.ipify.org').text
            self.external_ip = requests.get('https://ipv4.icanhazip.com').text
            self.share_ip = self.external_ip

        self.add_service("new_peer_connection", NewPeerProcessor(callback=self.new_peer_connection_service))
        self.add_service("peer_shutdown", PeerShutdownProcessor(callback=self.peer_shutdown_service))

        self.ctx = zmq.asyncio.Context()

        self.loop = None
        self.setup_event_loop()

        self.setup_publisher()
        self.setup_router()

        self.running = False

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
    def peer_list(self) -> List[Peer]:
        return list(self.peers.values())

    def log(self, log_type: str, message: str) -> None:
        named_message = f'[NETWORK] {message}'

        logger = get_logger(f'{self.external_address}')
        if log_type == 'info':
            logger.info(named_message)
        if log_type == 'error':
            logger.error(named_message)
        if log_type == 'warning':
            logger.warning(named_message)

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))  # Use Google's public DNS server as an example
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception as e:
            print("Error:", e)
            return None

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

    def set_to_local(self) -> None:
        self.local = True
        self.external_ip = '127.0.0.1'
        self.share_ip = self.get_local_ip()
        self.router.network_ip = self.external_address
        self.router.cred_provider.network_ip = self.external_address
        self.publisher.network_ip = self.external_address

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
        self.publisher.start()
        self.router.run_curve_server()
        self.running = True

    async def starting(self) -> None:
        while not self.publisher.is_running or not self.router.is_running:
            await asyncio.sleep(0.1)

    async def get_network_map_from_bootnode(self, ip: str, vk: str):
        peer = self.create_peer(ip=ip, vk=vk)
        peer.start(verify=False)
        response = await peer.get_network_map()
        await peer.stop()

        return response.get('network_map') if response else None

    def connect_peer(self, ip: str, vk: str) -> [bool, None]:
        if vk == self.vk:
            self.log('warning', f'Attempted connection to self "{vk[:8]}".')
            return

        if self.peers.get(vk):
            self.log('warning', f'Attempted to add an existing peer, vk: "{vk[:8]}" @ ip: {ip}')
            return

        if self.peer_is_voted_in(peer_vk=vk) or self.router.cred_provider.accept_all:
            self.add_peer(ip=ip, peer_vk=vk)
        else:
            self.log('warning', f'Attempted to add a peer not voted into network. "{vk}"')

    def peer_is_voted_in(self, peer_vk: str) -> bool:
        # Get list of approved nodes from state
        node_vk_list_from_smartcontracts = self.get_node_list()

        if peer_vk not in node_vk_list_from_smartcontracts:
            return False

        return True

    def refresh_approved_peers_in_cred_provider(self):
        node_vk_list_from_smartcontracts = self.get_node_list()
        self.router.refresh_cred_provider_vks(vk_list=node_vk_list_from_smartcontracts)
        self.log('info', f'Refreshed approved peers in credentials provider: {node_vk_list_from_smartcontracts}')

    def get_exiled_peers(self):
        exiles = []
        if not self.peer_is_voted_in(self.vk):
            exiles.append(self.vk)
        for peer_vk in self.peers.keys():
            if not self.peer_is_voted_in(peer_vk):
                exiles.append(peer_vk)

        return exiles

    async def check_connectivity(self):
        if len(self.peers) == 0:
            return True

        peers = list(self.peers.values())
        random.shuffle(peers)
        for peer in peers:
            if await peer.ping():
                return True

        return False

    def revoke_access_and_remove_peer(self, peer_vk):
        self.revoke_peer_access(peer_vk=peer_vk)
        self.remove_peer(peer_vk=peer_vk)

    def add_peer(self, ip: str, peer_vk: str):
        self.log('info', f'Adding new peer "{peer_vk[:8]}" @ {ip}')
        peer = self.create_peer(ip=ip, vk=peer_vk)
        self.peers[peer_vk] = peer
        self.start_peer(vk=peer_vk)

    def create_peer(self, ip: str, vk: str) -> Peer:
        return Peer(
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

    def add_service(self, name: str, processor: Processor) -> None:
        self.services[name] = processor

    def get_services(self) -> dict:
        return self.services

    def num_of_peers(self) -> int:
        return len(self.peer_list)

    def num_of_peers_connected(self) -> int:
        return len(list(filter(lambda x: x is True, [peer.is_connected for peer in self.peer_list])))

    def all_peers_connected(self):
        return self.num_of_peers() == self.num_of_peers_connected()

    def get_peer(self, vk: str) -> Peer:
        return self.peers.get(vk, None)

    def get_all_connected_peers(self) -> List[Peer]:
        return list(filter(lambda peer: peer.connected, self.peer_list))

    def delete_peer(self, peer_vk: str) -> None:
        self.peers.pop(peer_vk)

    def get_peer_by_ip(self, ip: str) -> [Peer, None]:
        for peer in self.peers.values():
            if ip == peer.ip:
                return peer
        return None

    def get_latest_block(self) -> dict:
        latest_block_num = get_latest_block_height(driver=self.driver)
        latest_block = self.block_storage.get_block(v=latest_block_num)

        if not latest_block:
            latest_block = {}

        return latest_block

    def get_latest_block_info(self) -> dict:
        latest_block = self.get_latest_block()

        return {
                'number': int(latest_block.get('number', 0)),
                'hlc_timestamp': latest_block.get('hlc_timestamp', '0'),
            }
    def get_highest_peer_block(self) -> int:
        highest_peer_block = 0
        for peer in self.get_all_connected_peers():
            if peer.latest_block_number > highest_peer_block:
                highest_peer_block = peer.latest_block_number

        return highest_peer_block

    async def refresh_peer_block_info(self) -> None:
        tasks = []
        for peer in self.peer_list:
            tasks.append(asyncio.ensure_future(peer.get_latest_block_info()))

        await asyncio.gather(*tasks)

    def set_socket_port(self, service: str, port_num: int) -> None:
        if not isinstance(port_num, int):
            raise AttributeError(EXCEPTION_PORT_NUM_NOT_INT)

        self.socket_ports[service] = port_num

    def authorize_peer(self, peer_vk: str) -> None:
        self.router.cred_provider.add_key(vk=peer_vk)

    def revoke_peer_access(self, peer_vk: str) -> None:
        self.router.cred_provider.remove_key(vk=peer_vk)

    def remove_peer(self, peer_vk: str) -> None:
        if not self.get_peer(vk=peer_vk):
            return

        asyncio.ensure_future(self.stop_and_delete_peer(peer_vk=peer_vk))

    async def stop_and_delete_peer(self, peer_vk):
        peer = self.get_peer(vk=peer_vk)

        if not peer:
            return

        await peer.stop()

        self.delete_peer(peer_vk=peer_vk)
        self.log('info', f'Stopped and removed peer: "{peer_vk}"')

    def start_peer(self, vk: str) -> None:
        self.peers[vk].start()

    def connected_to_peer_callback(self, peer_vk: str) -> [bool, None]:
        peer = self.get_peer(vk=peer_vk)

        if not peer:
            return

        ip = peer.request_address

        self.publisher.announce_new_peer_connection(ip=ip, vk=peer_vk)


    def new_peer_connection_service(self, msg: dict) -> None:
        if not msg:
            return

        peer_vk = msg.get('vk')

        if peer_vk is None:
            return

        if peer_vk != self.vk and not self.peers.get(peer_vk):
            peer_ip = msg.get('ip')

            if peer_ip is None:
                return

            self.connect_peer(ip=peer_ip, vk=peer_vk)

    def peer_shutdown_service(self, msg: dict):
        if not msg:
            return
        self.remove_peer(msg.get('vk'))

    async def connected_to_all_peers(self) -> bool:
        self.log('info', f'Establishing connection with {self.num_of_peers()} peers...')

        while self.num_of_peers_connected() < self.num_of_peers():
            await asyncio.sleep(1)

            peers_connected = list()
            peers_not_connected = list()

            for peer in self.peer_list:
                if peer.connected:
                    peers_connected.append(peer.request_address)
                else:
                    peers_not_connected.append(peer.request_address)

            self.log('info', f'Connected to: {peers_connected}')
            self.log('warning', f'Awaiting connection to: {peers_not_connected}')

        self.log('info', f'Connected to all {self.num_of_peers()} peers!')

    def make_network_map(self) -> dict:
        return {
            'masternodes': self.map_vk_to_ip(self.get_node_list())
        }

    def network_map_to_node_list(self, network_map: dict = dict({})) -> list:
        node_list = []

        for vk, ip in network_map['masternodes'].items():
            node_list.append({'vk': vk, 'ip': ip})

        return node_list

    def get_node_ip(self, vk):
        if vk == self.wallet.verifying_key:
            return self.share_ip
        else:
            peer = self.get_peer(vk=vk)
            if peer is not None:
                if peer.ip is not None:
                    return peer.ip

        return None

    def get_bootnode_ips(self):
        ips = []
        for vk in self.get_node_list():
            if vk != self.wallet.verifying_key:
                ips.append(self.get_node_ip(vk))

        ips.reverse()
        return ips

    def map_vk_to_ip(self, vk_list: list, only_ip=False) -> dict:
        vk_to_ip_map = dict()

        for vk in vk_list:
            if vk == self.wallet.verifying_key:
                vk_to_ip_map[vk] = self.external_address if not only_ip else self.share_ip
            else:
                peer = self.get_peer(vk=vk)
                if peer is not None:
                    if peer.ip is not None:
                        vk_to_ip_map[vk] = peer.request_address if not only_ip else peer.ip

        return vk_to_ip_map

    def get_node_list(self) -> list:
        return self.driver.driver.get('masternodes.S:members') or []

    def hello_response(self, challenge: str = None) -> str:
        latest_block_info = self.get_latest_block_info()

        block_num = latest_block_info.get('number')
        hlc_timestamp = latest_block_info.get("hlc_timestamp")

        try:
            challenge_response = self.wallet.sign(challenge)
        except:
            challenge_response = ""

        return '{"response":"%s", "challenge_response": "%s","latest_block_number": %d, "latest_hlc_timestamp": "%s"}' % (ACTION_HELLO, challenge_response, block_num, hlc_timestamp)

    async def router_callback(self, ident_vk_bytes: bytes, ident_vk_string: str, msg: str) -> None:
        try:
            msg = decode(msg)
            action = msg.get('action')
        except Exception as err:
            self.log('error', str(err))
            return

        if action == ACTION_PING:
            self.router.send_msg(
                ident_vk_bytes=ident_vk_bytes,
                to_vk=ident_vk_string,
                msg_str=encode({"response": "ping", "from": ident_vk_string})
            )

        if action == ACTION_HELLO:
            ip = msg.get('ip')
            challenge = msg.get('challenge')

            self.router.send_msg(
                ident_vk_bytes=ident_vk_bytes,
                to_vk=ident_vk_string,
                msg_str=self.hello_response(challenge=challenge)
            )

            if not self.peers.get(ident_vk_string):
                self.connect_peer(vk=ident_vk_string, ip=ip)

        if action == ACTION_GET_LATEST_BLOCK:
            latest_block_info = self.get_latest_block_info()
            block_num = latest_block_info.get('number')
            hlc_timestamp = latest_block_info.get("hlc_timestamp")

            resp_msg = ('{"response": "%s", "latest_block_number": %d, "latest_hlc_timestamp": "%s"}' % (ACTION_GET_LATEST_BLOCK, block_num, hlc_timestamp))

            self.router.send_msg(
                ident_vk_bytes=ident_vk_bytes,
                to_vk=ident_vk_string,
                msg_str=resp_msg
            )
            self.log('info', f'Sent back latest block info: {latest_block_info}')

        if action == ACTION_GET_BLOCK:
            block_num = msg.get('block_num', None)
            hlc_timestamp = msg.get('hlc_timestamp', None)
            if isinstance(block_num, int) or hlc.is_hcl_timestamp(hlc_timestamp):
                block_info = self.block_storage.get_block(v=block_num or hlc_timestamp)
                block_info = encode(block_info)

                self.router.send_msg(
                    ident_vk_bytes=ident_vk_bytes,
                    to_vk=ident_vk_string,
                    msg_str=('{"response": "%s", "block_info": %s}' % (ACTION_GET_BLOCK, block_info))
                )

        if action == ACTION_GET_NEXT_BLOCK:
            block_num = msg.get('block_num')
            hlc_timestamp = msg.get('hlc_timestamp')
            v = block_num
            if not isinstance(block_num, int):
                if hlc.is_hcl_timestamp(hlc_timestamp):
                    v = hlc_timestamp
                else:
                    return

            block_info = self.block_storage.get_next_block(v=v)
            block_info = encode(block_info)

            self.router.send_msg(
                ident_vk_bytes=ident_vk_bytes,
                to_vk=ident_vk_string,
                msg_str=('{"response": "%s", "block_info": %s}' % (ACTION_GET_NEXT_BLOCK, block_info))
            )

            self.log('warning', f'sent block num {block_num}')

        if action == ACTION_GET_NETWORK_MAP:
            node_list = encode(self.make_network_map())

            resp_msg = ('{"response": "%s", "network_map": %s}' % (ACTION_GET_NETWORK_MAP, node_list))

            self.router.send_msg(
                ident_vk_bytes=ident_vk_bytes,
                to_vk=ident_vk_string,
                msg_str=resp_msg
            )

    async def stop(self):
        self.publisher.announce_shutdown(vk=self.wallet.verifying_key)
        self.running = False

        tasks = []
        for peer in self.peers.values():
            task = asyncio.ensure_future(peer.stop())
            tasks.append(task)

        await asyncio.gather(*tasks)

        self.publisher.stop()
        await self.router.stop()

        self.ctx.destroy(linger=0)

        self.log('info', 'Stopped.')
