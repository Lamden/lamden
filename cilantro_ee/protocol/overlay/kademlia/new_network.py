from cilantro_ee.constants import conf
from cilantro_ee.constants.ports import DHT_PORT
from cilantro_ee.protocol.comm import services
from cilantro_ee.protocol.wallet import Wallet

from cilantro_ee.protocol.overlay.kademlia.routing import RoutingTable
from cilantro_ee.protocol.overlay.kademlia.node import Node
from cilantro_ee.protocol.overlay.kademlia.utils import digest

from cilantro_ee.protocol.overlay.kademlia.discovery import DiscoveryServer, discover_nodes
from cilantro_ee.constants.ports import DISCOVERY_PORT
from cilantro_ee.constants.overlay_network import PEPPER
from cilantro_ee.storage.vkbook import PhoneBook

import asyncio

import zmq
import hashlib
from cilantro_ee.logger.base import get_logger


log = get_logger('NetworkService')


def digest_from_vk(b: bytes):
    h = hashlib.sha3_256()
    h.update(b)
    return h.digest()


class RPCServer(services.RequestReplyService):
    def __init__(self, address: str, wallet: Wallet, ctx=zmq.Context):
        super().__init__(address=address, wallet=wallet, ctx=ctx)

        self.is_connected = False

        digest = digest_from_vk(self.wallet.verifying_key())
        self.dht_id = Node(node_id=digest,
                           ip=self.ip,
                           port=DHT_PORT,
                           vk=self.wallet.verifying_key().hex())

        self.routing_table = RoutingTable(self.dht_id)

    def handle_msg(self, msg):
        # Cast to bytearray for easier manipulation
        msg = bytearray(msg)

        # First byte determines command
        command = msg.pop(0)

        if command == 0 and len(msg) == 68:
            ip = [str(byte) for byte in msg[0:4]]
            ip = '.'.join(ip)

            sender_vk = msg[4:36]
            requested_vk = msg[36:]

            return self.rpc_find_ip(ip, sender_vk, requested_vk)

        elif command == 1:
            # do the other one
            return self.rpc_ping_ip()

    def rpc_find_ip(self, ip, sender_vk, requested_vk):
        if self.is_connected and sender_vk == requested_vk:
            pass

        requested_digest = digest_from_vk(requested_vk)
        requested_node = Node(node_id=requested_digest,
                              vk=requested_vk)

        nodes = self.routing_table.find_node(requested_node)
        return nodes

    @staticmethod
    def rpc_ping_ip():
        return b''


class NewNetwork:
    def __init__(self, wallet, ctx:zmq.Context):
        self.wallet = wallet
        self.ctx = ctx

        self.ip = conf.HOST_IP

        # Configure node ID for DHT storage
        digest = digest_from_vk(self.wallet.verifying_key())
        self.dht_id = Node(node_id=digest,
                           ip=self.ip,
                           port=DHT_PORT,
                           vk=self.wallet.verifying_key().hex())

        self.routing_table = RoutingTable(self.dht_id)

        discovery_address = 'tcp://*:{}'.format(DISCOVERY_PORT)
        self.log.info('Setting up Discovery Server on {}.'.format(discovery_address))
        self.discovery_server = DiscoveryServer(address=discovery_address,
                                                wallet=self.wallet,
                                                pepper=PEPPER.encode(),
                                                ctx=self.ctx)

        self.tasks = []

        if self.wallet.verifying_key().hex() in PhoneBook.masternodes:
            self.tasks.append(self.discovery_server.serve())

    async def bootup(self):
        ip_list = conf.BOOTNODES

        # Remove our own IP so that we don't respond to ourselves.
        if conf.HOST_IP in ip_list:
            ip_list.remove(conf.HOST_IP)

        log.info('Pinging {} for discovery...'.format(ip_list))

        addrs = await discover_nodes(ip_list, pepper=PEPPER.encode(), ctx=self.ctx)

        if len(addrs):
            log.success('Found {} node(s). Putting them in the DHT.'.format(len(addrs)))

            nodes = [Node(digest(vk), ip=ip, port=self.port, vk=vk) for ip, vk in addrs.items()]

            if not self.discovery_server.running:
                log.info('Discovery server was not running. Starting it now so others can find us.')
                asyncio.ensure_future(self.discovery_server.serve())

            log.success('Going into bootstrap!')
            await self.bootstrap(nodes)

        else:
            raise Exception('Failed to discover any nodes.')