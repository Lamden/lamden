from os import getenv as env

from cilantro_ee.constants import conf
from cilantro_ee.constants.ports import DHT_PORT
from cilantro_ee.networking.parameters import ServiceType, NetworkParameters
from cilantro_ee.networking.peers import KTable, PeerServer
from cilantro_ee.networking import discovery
from cilantro_ee.sockets import services

from copy import deepcopy
import asyncio
import json
import zmq
from cilantro_ee.logger.base import get_logger

import random

log = get_logger('NetworkService')

class Network:
    def __init__(self, wallet,
                 params=NetworkParameters(),
                 ctx=zmq.asyncio.Context(),
                 bootnodes=conf.BOOT_DELEGATE_IP_LIST + conf.BOOT_MASTERNODE_IP_LIST,
                 initial_mn_quorum=1,
                 initial_del_quorum=1,
                 mn_to_find=[],
                 del_to_find=[],
                 socket_base='tcp://127.0.0.1',
                 poll_timeout=10,
                 linger=500):

        # General Instance Variables
        self.wallet = wallet
        self.ctx = ctx

        self.bootnodes = bootnodes
        self.ip = socket_base

        data = {
            self.wallet.verifying_key().hex(): socket_base
        }

        self.table = KTable(data=data)

        # Peer Service Constants
        self.params = params

        self.peer_service_address = self.params.resolve(socket_base, ServiceType.PEER, bind=True)
        self.event_server_address = self.params.resolve(socket_base, ServiceType.EVENT, bind=True)
        self.peer_service = PeerServer(self.peer_service_address,
                                       event_address=self.event_server_address,
                                       table=self.table, wallet=self.wallet, ctx=self.ctx, poll_timeout=poll_timeout, linger=linger)

        self.discovery_server_address = self.params.resolve(socket_base, ServiceType.DISCOVERY, bind=True)
        self.discovery_server = discovery.DiscoveryServer(self.discovery_server_address,
                                                          wallet=self.wallet,
                                                          pepper=PEPPER.encode(),
                                                          ctx=self.ctx,
                                                          poll_timeout=poll_timeout, linger=linger)



        # Quorum Constants
        self.initial_mn_quorum = initial_mn_quorum
        self.initial_del_quorum = initial_del_quorum
        self.mn_to_find = mn_to_find
        self.del_to_find = del_to_find
        self.ready = False

    async def start(self, discover=True):
        # Start the Peer Service and Discovery service
        await self.peer_service.start()

        if discover:
            if self.wallet.verifying_key().hex() in self.mn_to_find:
                asyncio.ensure_future(
                    self.discovery_server.serve()
                )
            # Discover our bootnodes

            discovery_sockets = \
                [self.params.resolve(bootnode, ServiceType.DISCOVERY) for bootnode in self.bootnodes]

            await self.discover_bootnodes(discovery_sockets)

            # If bootnodes are IPC, append to the path 'peer-service'
            # Otherwise, add the peer service port

            peer_sockets = \
                [self.params.resolve(bootnode, ServiceType.PEER) for bootnode in self.bootnodes]

            log.info('Peers now: {}'.format(peer_sockets))

            # Wait for the quorum to resolve
            await self.wait_for_quorum(
                self.initial_mn_quorum,
                self.initial_del_quorum,
                self.mn_to_find,
                self.del_to_find,
                peer_sockets
            )

            log.success('Network is ready.')

            self.ready = True

            ready_msg = json.dumps({'event': 'service_status', 'status': 'ready'}, cls=services.SocketEncoder).encode()

            await self.peer_service.event_publisher.send(ready_msg)

            log.success('Sent ready signal.')

    async def discover_bootnodes(self, nodes):
        responses = await discovery.discover_nodes(nodes, pepper=PEPPER.encode(),
                                                   ctx=self.ctx, timeout=500)

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
            await services.get(peer, msg=join_message, ctx=self.ctx, timeout=500)

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

        if not self.discovery_server.running:
            asyncio.ensure_future(
                self.discovery_server.serve()
            )

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
            try:
                all_nodes.remove(vk)
            except:
                pass

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
            response = await services.get(client_address, msg=find_message, ctx=self.ctx, timeout=500)

            if response is None:
                return None

            response = json.loads(response.decode())

        if response.get(vk_to_find) is not None:
            return response

        if retries <= 1:
            return None

        # Recursive crawl goes 'retries' levels deep
        for vk, ip in response.items():
            return await self.find_node(services.SocketStruct(services.Protocols.TCP, ip, DHT_PORT), vk_to_find, retries=retries - 1)

    def stop(self):
        self.peer_service.stop()


PEPPER = env('PEPPER', 'cilantro_pepper')