from cilantro_ee.constants import conf
from cilantro_ee.constants.ports import DHT_PORT, DISCOVERY_PORT, EVENT_PORT
from cilantro_ee.constants.overlay_network import PEPPER
from cilantro_ee.protocol.overlay.kademlia import discovery
from cilantro_ee.protocol.comm import services
from cilantro_ee.protocol.wallet import Wallet

from cilantro_ee.storage.vkbook import PhoneBook

from functools import partial
import asyncio
import json
import zmq
from cilantro_ee.logger.base import get_logger

import random

log = get_logger('NetworkService')


def bytes_from_ip_string(ip: str):
    b = ip.split('.')
    bb = [int(i) for i in b]
    return bytes(bb)


class KTable:
    def __init__(self, data: dict, initial_peers={}, response_size=10):
        self.data = data
        self.peers = initial_peers
        self.response_size = response_size

    @staticmethod
    def distance(string_a, string_b):
        int_val_a = int(string_a.encode().hex(), 16)
        int_val_b = int(string_b.encode().hex(), 16)
        return int_val_a ^ int_val_b

    def find(self, key):
        if key in self.data:
            return self.data
        elif key in self.peers:
            return {
                key: self.peers[key]
            }
        else:
            # Do an XOR sort on all the keys to find neighbors
            sort_func = partial(self.distance, string_b=key)
            closest_peer_keys = sorted(self.peers.keys(), key=sort_func)

            # Only keep the response size number
            closest_peer_keys = closest_peer_keys[:self.response_size]

            # Dict comprehension
            neighbors = {k: self.peers[k] for k in closest_peer_keys}

            return neighbors


class PeerServer(services.RequestReplyService):
    def __init__(self, address: str, event_publisher_address: str, table: KTable, wallet: Wallet, ctx=zmq.Context,
                 linger=2000, poll_timeout=500):

        super().__init__(address=address,
                         wallet=wallet,
                         ctx=ctx,
                         linger=linger,
                         poll_timeout=poll_timeout)

        self.table = table

        self.event_service = services.SubscriptionService(ctx=self.ctx)
        self.event_publisher = self.ctx.socket(zmq.PUB)
        self.event_publisher.bind(event_publisher_address)

        self.event_queue_loop_running = False

    def handle_msg(self, msg):
        msg = msg.decode()
        command, args = json.loads(msg)

        if command == 'find':
            response = self.table.find(args)
            response = json.dumps(response).encode()
            return response
        if command == 'join':
            vk, ip = args # unpack args
            asyncio.ensure_future(self.handle_join(vk, ip))
            return None

    async def handle_join(self, vk, ip):
        result = self.table.find(vk)

        if vk not in result or result[vk] != ip:
            # Ping discovery server
            _, responded_vk = await discovery.ping(ip, pepper=PEPPER.encode(), ctx=self.ctx, timeout=1000)

            if responded_vk.hex() == vk:
                # Valid response
                self.table.peers[vk] = ip

                # Publish a message that a new node has joined
                msg = ('join', (vk, ip))
                jmsg = json.dumps(msg).encode()
                await self.event_publisher.send(jmsg)

    async def process_event_subscription_queue(self):
        self.event_queue_loop_running = True

        while self.event_queue_loop_running:
            if len(self.event_service.received) > 0:
                message, sender = self.event_service.received.pop(0)
                msg = json.loads(message.decode())
                command, args = msg
                vk, ip = args

                if command == 'join':
                    asyncio.ensure_future(self.handle_join(vk=vk, ip=ip))

                elif command == 'leave':
                    # Ping to make sure the node is actually offline
                    _, responded_vk = await discovery.ping(ip, pepper=PEPPER.encode(),
                                                           ctx=self.ctx, timeout=1000)

                    # If so, remove it from our table
                    if responded_vk is None:
                        del self.table[vk]

            await asyncio.sleep(0)

    async def start(self):
        asyncio.ensure_future(asyncio.gather(
            self.serve(),
            self.event_service.serve(),
            self.process_event_subscription_queue()
        ))

    def stop(self):
        self.running = False
        self.event_queue_loop_running = False
        self.event_service.running = False


class Network:
    def __init__(self, wallet, peer_service_port: int=DHT_PORT, event_publisher_port: int=EVENT_PORT,
                 ctx=zmq.asyncio.Context(), ip=conf.HOST_IP,
                 bootnodes=conf.BOOT_DELEGATE_IP_LIST + conf.BOOT_MASTERNODE_IP_LIST):

        self.wallet = wallet
        self.ctx = ctx

        self.bootnodes = bootnodes

        self.peer_service_address = 'tcp://{}:{}'.format(ip, peer_service_port)

        data = {
            self.wallet.verifying_key().hex(): self.peer_service_address
        }
        self.table = KTable(data=data)

        self.event_publisher_address = 'tcp://*:{}'.format(event_publisher_port)
        self.peer_service = PeerServer(address=self.peer_service_address,
                                       event_publisher_address=self.event_publisher_address,
                                       table=self.table, wallet=self.wallet, ctx=self.ctx)

    async def discover_bootnodes(self):
        responses = await discovery.discover_nodes(self.bootnodes, pepper=PEPPER.encode(),
                                                   ctx=self.ctx, timeout=100)

        for ip, vk in responses.items():
            self.table.peers[vk] = ip  # Should be stripped of port and tcp

        # Crawl bootnodes 'announcing' yourself.
        await self.wait_for_quorum()

    async def wait_for_quorum(self):
        # Determine how many more nodes we need to find
        masternodes_left = PhoneBook.masternode_quorum_min
        delegates_left = PhoneBook.delegate_quorum_min

        # Storing these in local vars saves DB hits
        current_masternodes = PhoneBook.masternodes
        current_delegates = PhoneBook.delegates

        current_peers = {}
        current_peers.update(self.table.peers)
        current_peers.update(self.table.data)

        # Try to find all of the nodes that are online

        #all_nodes = self.
        while masternodes_left > 0 and delegates_left > 0:
            total_nodes_online = await asyncio.wait(
                self.find_node(client_address=random.choice(self.bootnodes),
                               vk_to_find=vk,
                               retries=3) for vk in current_masternodes + current_delegates
            )

            print(total_nodes_online)

    async def find_node(self, client_address, vk_to_find, retries=3):
        # Search locally if this is the case
        if client_address == self.peer_service_address:
            response = self.table.find(vk_to_find)

        # Otherwise, send out a network request
        else:
            find_message = ['find', vk_to_find]
            find_message = json.dumps(find_message).encode()

            response = await services.get(client_address, msg=find_message, ctx=self.ctx, timeout=1000)
            response = json.loads(response.decode())

        if response.get(vk_to_find) is not None:
            return response

        if retries <= 1:
            return None

        # Recursive crawl goes 'retries' levels deep
        for vk, ip in response.items():
            return await self.find_node(ip, vk_to_find, retries=retries-1)
