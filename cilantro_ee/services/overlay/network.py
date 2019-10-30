from cilantro_ee.constants import conf
from cilantro_ee.constants.ports import DHT_PORT, DISCOVERY_PORT, EVENT_PORT
from cilantro_ee.constants.overlay_network import PEPPER
from cilantro_ee.services.overlay import discovery
from cilantro_ee.core.sockets import services
from cilantro_ee.core.crypto.wallet import Wallet

from copy import deepcopy
from functools import partial
import asyncio
import json
import zmq
from cilantro_ee.core.logger.base import get_logger

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
    def __init__(self, socket_id: services.SocketStruct,
                 event_port: int,
                 discovery_port: int,
                 table: KTable, wallet: Wallet, ctx=zmq.Context,
                 linger=2000, poll_timeout=3000, pepper=PEPPER.encode()):

        super().__init__(socket_id=socket_id,
                         wallet=wallet,
                         ctx=ctx,
                         linger=linger,
                         poll_timeout=poll_timeout)

        self.table = table

        self.event_address = 'tcp://*:{}'.format(event_port)
        self.event_service = services.SubscriptionService(ctx=self.ctx)

        self.event_publisher = self.ctx.socket(zmq.PUB)
        self.event_publisher.bind(self.event_address)

        self.event_queue_loop_running = False

        self.discovery_port = discovery_port

    def handle_msg(self, msg):
        msg = msg.decode()
        command, args = json.loads(msg)

        if command == 'find':
            response = self.table.find(args)
            response = json.dumps(response, cls=services.SocketEncoder).encode()
            return response
        if command == 'join':
            vk, ip = args # unpack args
            asyncio.ensure_future(self.handle_join(vk, ip))
            return None
        #if command == 'ping':
        #    return self.ping_response

    async def handle_join(self, vk, ip):
        result = self.table.find(vk)

        if vk not in result or result[vk] != ip:
            # Ping discovery server
            _, responded_vk = await discovery.ping(services._socket(ip),
                                    pepper=PEPPER.encode(), ctx=self.ctx, timeout=1000)

            await asyncio.sleep(0)
            if responded_vk is None:
                return

            if responded_vk.hex() == vk:
                # Valid response
                self.table.peers[vk] = ip

                # Publish a message that a _new node has joined
                msg = ['join', (vk, ip)]
                jmsg = json.dumps(msg, cls=services.SocketEncoder).encode()
                await self.event_publisher.send(jmsg)

                second_msg = json.dumps({'event': 'node_online', 'vk': vk, 'ip': services._socket(ip).id}, cls=services.SocketEncoder).encode()
                await self.event_publisher.send(second_msg)

    async def process_event_subscription_queue(self):
        self.event_queue_loop_running = True

        while self.event_queue_loop_running:
            if len(self.event_service.received) > 0:
                message, sender = self.event_service.received.pop(0)
                msg = json.loads(message.decode())

                # Ignore event dictionaries
                if isinstance(msg, dict):
                    continue

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
        log.info('Peer services running on {}'.format(self.address))

    def stop(self):
        self.running = False
        self.event_queue_loop_running = False
        self.event_service.running = False


class Network:
    def __init__(self, wallet,
                 peer_service_port: int=DHT_PORT,
                 event_publisher_port: int=EVENT_PORT,
                 discovery_port: int=DISCOVERY_PORT,
                 ctx=zmq.asyncio.Context(),
                 ip=conf.HOST_IP,
                 bootnodes=conf.BOOT_DELEGATE_IP_LIST + conf.BOOT_MASTERNODE_IP_LIST,
                 initial_mn_quorum=1,
                 initial_del_quorum=1,
                 mn_to_find=[],
                 del_to_find=[]):

        # General Instance Variables
        self.wallet = wallet
        self.ctx = ctx

        self.bootnodes = bootnodes
        self.ip = ip

        # Peer Service Constants
        self.peer_service_address = services.SocketStruct(services.Protocols.TCP, '*', peer_service_port)

        data = {
            self.wallet.verifying_key().hex(): ip
        }
        self.table = KTable(data=data)

        self.event_publisher_address = 'tcp://*:{}'.format(event_publisher_port)
        self.peer_service_port = peer_service_port
        self.peer_service = PeerServer(self.peer_service_address,
                                       event_port=event_publisher_port,
                                       discovery_port=discovery_port,
                                       table=self.table, wallet=self.wallet, ctx=self.ctx)

        self.discovery_port = discovery_port
        self.discovery_server_address = services.SocketStruct(services.Protocols.TCP, '*', self.discovery_port)
        self.discovery_server = discovery.DiscoveryServer(self.discovery_server_address,
                                                          wallet=self.wallet,
                                                          pepper=PEPPER.encode(),
                                                          ctx=self.ctx)

        # Quorum Constants
        self.initial_mn_quorum = initial_mn_quorum
        self.initial_del_quorum = initial_del_quorum
        self.mn_to_find = mn_to_find
        self.del_to_find = del_to_find
        self.ready = False

    async def start(self):
        # Start the Peer Service and Discovery service
        asyncio.ensure_future(
            self.peer_service.start()
        )

        if self.wallet.verifying_key().hex() in self.mn_to_find:
            asyncio.ensure_future(
                self.discovery_server.serve()
            )

        discovery_bootnode_ids = [services.SocketStruct(services.Protocols.TCP, ip, self.discovery_port)
                                     for ip in self.bootnodes]

        # Discover our bootnodes
        await self.discover_bootnodes(discovery_bootnode_ids)

        peer_service_bootnode_ids = [services.SocketStruct(services.Protocols.TCP, ip, self.peer_service_port)
                                     for ip in self.bootnodes]

        log.info('Peers now: {}'.format(self.bootnodes))

        # Wait for the quorum to resolve
        await self.wait_for_quorum(
            self.initial_mn_quorum,
            self.initial_del_quorum,
            self.mn_to_find,
            self.del_to_find,
            peer_service_bootnode_ids
        )

        log.success('Network is ready.')

        self.ready = True

        ready_msg = json.dumps({'event': 'service_status', 'status': 'ready'}, cls=services.SocketEncoder).encode()

        await self.peer_service.event_publisher.send(ready_msg)

        log.success('Sent ready signal.')
        return

    async def discover_bootnodes(self, nodes):
        responses = await discovery.discover_nodes(nodes, pepper=PEPPER.encode(),
                                                   ctx=self.ctx, timeout=3000)

        log.info(responses)

        for ip, vk in responses.items():
            self.table.peers[vk] = ip  # Should be stripped of port and tcp

        if not self.discovery_server.running:
            asyncio.ensure_future(self.discovery_server.serve())

        # Ping everyone discovered that you've joined

        current_nodes = deepcopy(self.table.peers)
        for vk, ip in current_nodes.items():
            join_message = ['join', (self.wallet.verifying_key().hex(), self.ip)]
            join_message = json.dumps(join_message, cls=services.SocketEncoder).encode()

            peer = services.SocketStruct(services.Protocols.TCP, ip, DHT_PORT)
            await services.get(peer, msg=join_message, ctx=self.ctx, timeout=3000)

    async def wait_for_quorum(self, masternode_quorum_required: int,
                                    delegate_quorum_required: int,
                                    masternodes_to_find: list,
                                    delegates_to_find: list,
                                    initial_peers: list,
                                    ):

        results = None


        # Crawl while there are still nodes needed in our quorum
        while masternode_quorum_required > 0 or delegate_quorum_required > 0:
            # Create task lists
            log.info('Need {} MNs and {} DELs to begin...'.format(
                masternode_quorum_required,
                delegate_quorum_required
            ))

            master_crawl = [self.find_node(client_address=random.choice(initial_peers),
                            vk_to_find=vk, retries=3) for vk in masternodes_to_find]

            delegate_crawl = [self.find_node(client_address=random.choice(initial_peers),
                              vk_to_find=vk, retries=3) for vk in delegates_to_find]

            # Crawl for both node types
            crawl = asyncio.gather(*master_crawl, *delegate_crawl)

            results = await crawl

            # Split the result list
            masters_got = results[:len(masternodes_to_find)]
            delegates_got = results[len(masternodes_to_find):]

            masternode_quorum_required = self.updated_peers_and_crawl(masters_got,
                                                                      masternodes_to_find,
                                                                      masternode_quorum_required)

            delegate_quorum_required = self.updated_peers_and_crawl(delegates_got,
                                                                    delegates_to_find,
                                                                    delegate_quorum_required)

        # At this point, start the discovery server if it's not already running because you are a masternode.

        log.success('Quorum reached! Begin protocol services...')

        return results

    def updated_peers_and_crawl(self, node_results, all_nodes, current_quorum):
        nodes = {}

        # Pack successful requests into a dictionary
        for node in node_results:
            if node is not None:
                nodes.update(node)

        # Update the peer table with the _new nodes
        self.table.peers.update(nodes)

        # Remove the nodes from the all_nodes list. Don't need to query them again
        for vk, _ in nodes.items():
            all_nodes.remove(vk)

        # Return the number of nodes needed left
        return current_quorum - len(nodes)

    # Returns raw IP string for a node: 127.0.0.1 etc. Transform this into whatever you want.
    async def find_node(self, client_address: services.SocketStruct=None, vk_to_find=None, retries=3):
        # Search locally if this is the case
        if str(client_address) == str(self.peer_service_address) or \
                vk_to_find == self.wallet.verifying_key().hex() or \
                client_address is None:
            response = self.table.find(vk_to_find)

        # Otherwise, send out a network request
        else:
            find_message = ['find', vk_to_find]
            find_message = json.dumps(find_message, cls=services.SocketEncoder).encode()
            response = await services.get(client_address, msg=find_message, ctx=self.ctx, timeout=3000)

            if response is None:
                return None

            response = json.loads(response.decode())

        if response.get(vk_to_find) is not None:
            return response

        if retries <= 1:
            return None

        # Recursive crawl goes 'retries' levels deep
        for vk, ip in response.items():
            return await self.find_node(services.SocketStruct(services.Protocols.TCP, ip, DHT_PORT), vk_to_find, retries=retries-1)
