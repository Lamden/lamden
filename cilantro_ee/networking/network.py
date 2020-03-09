from cilantro_ee.networking.parameters import ServiceType, NetworkParameters, DHT_PORT, PEPPER
from cilantro_ee.networking.peers import PeerServer
from cilantro_ee.networking import discovery
from cilantro_ee.sockets import services, struct

from copy import deepcopy
import asyncio
import json
import zmq
from cilantro_ee.logger.base import get_logger

import random


class Network:
    def __init__(self, wallet,
                 params=NetworkParameters(),
                 ctx=zmq.asyncio.Context(),
                 bootnodes=[],
                 initial_mn_quorum=1,
                 initial_del_quorum=1,
                 mn_to_find=[],
                 del_to_find=[],
                 socket_base='tcp://0.0.0.0',
                 poll_timeout=200,
                 linger=1000,
                 debug=True,
                 mn_seed=None):

        self.log = get_logger('NetworkService')
        self.log.propagate = debug

        self.mn_seed = mn_seed # Set this to a single masternode if you are joining the network!!

        # General Instance Variables
        self.wallet = wallet
        self.ctx = ctx

        self.bootnodes = bootnodes
        self.ip = socket_base

        # Peer Service Constants
        self.params = params

        self.socket_base = socket_base

        self.peer_service_address = self.params.resolve(socket_base, ServiceType.PEER, bind=True)
        self.event_server_address = self.params.resolve(socket_base, ServiceType.EVENT, bind=True)
        self.peer_service = PeerServer(self.peer_service_address,
                                       event_address=self.event_server_address,
                                       table={
                                           self.wallet.verifying_key().hex(): socket_base
                                       },
                                       wallet=self.wallet,
                                       ctx=self.ctx,
                                       poll_timeout=poll_timeout,
                                       linger=linger
                                       )

        self.discovery_server_address = self.params.resolve(self.socket_base, ServiceType.DISCOVERY, bind=True)
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

        self.outbox = services.Outbox(self.ctx)

    async def start(self, discover=True):
        # Start the Peer Service and Discovery service
        await self.peer_service.start()

        if discover:
            #if self.wallet.verifying_key().hex() in self.mn_to_find or self.mn_seed is not None:
            asyncio.ensure_future(
                self.discovery_server.serve() # Start this when joining network so mn_seed can verify you
            )
            # Discover our bootnodes

            discovery_sockets = \
                [self.params.resolve(bootnode, ServiceType.DISCOVERY) for bootnode in self.bootnodes]

            await self.discover_bootnodes(discovery_sockets)

            # If bootnodes are IPC, append to the path 'peer-service'
            # Otherwise, add the peer service port

            peer_sockets = \
                [self.params.resolve(bootnode, ServiceType.PEER) for bootnode in self.bootnodes]

            self.log.info('Peers now: {}'.format(peer_sockets))

            #self.peer_service.table.peers = peer_sockets

            # Wait for the quorum to resolve

            # IF THE BLOCKCHAIN IS JUST STARTING DO THIS
            if self.mn_seed is None:
                await self.wait_for_quorum(
                    self.initial_mn_quorum,
                    self.initial_del_quorum,
                    self.mn_to_find,
                    self.del_to_find,
                    peer_sockets
                )
            else:
                await self.get_current_contacts()

            # OTHERWISE, DO SOMETHING ELSE.

            self.log.success('Network is ready.')

            self.ready = True

            ready_msg = json.dumps({'event': 'service_status', 'status': 'ready'}, cls=struct.SocketEncoder).encode()

            await self.peer_service.event_publisher.send(ready_msg)

            self.log.success('Sent ready signal.')

    async def get_current_contacts(self):
        # Send a join
        self.log.info('Joining network...')
        join_message = ['join', (self.wallet.verifying_key().hex(), self.socket_base)]
        join_msg = json.dumps(join_message).encode()

        self.log.info(f'mn seed: {self.mn_seed}')

        master_socket = self.params.resolve(
            self.mn_seed,
            ServiceType.PEER
        )

        self.log.info(f'Sending {join_msg} for {str(master_socket)}')

        await services.get(
            master_socket, msg=join_msg, ctx=self.ctx, timeout=1000
        )

        # Ask for the current people online
        ask_message = ['ask', '']
        ask_msg = json.dumps(ask_message).encode()

        resp = await services.get(
            master_socket, msg=ask_msg, ctx=self.ctx, timeout=1000
        )

        contacts = json.loads(resp)

        self.log.info(f'Got contacts: {contacts}')

        self.peer_service.table = contacts

    async def discover_bootnodes(self, nodes):
        responses = await discovery.discover_nodes(nodes, pepper=PEPPER.encode(),
                                                   ctx=self.ctx, timeout=1000)

        for ip, vk in responses.items():
            self.peer_service.table[vk] = struct.strip_service(ip)  # Should be stripped of port and tcp
            self.log.error(f'Added {struct.strip_service(ip)} for {vk}')

        #if not self.discovery_server.running:
        #    asyncio.ensure_future(self.discovery_server.serve())

        # Ping everyone discovered that you've joined

        current_nodes = deepcopy(self.peer_service.table)
        for vk, ip in current_nodes.items():
            join_message = ['join', (self.wallet.verifying_key().hex(), self.ip)]
            join_message = json.dumps(join_message, cls=struct.SocketEncoder).encode()

            peer = self.params.resolve(ip, service_type=ServiceType.PEER)
            self.log.error(peer)

            await services.get(peer, msg=join_message, ctx=self.ctx, timeout=1000)

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
            self.log.info('Need {} MNs and {} DELs to begin...'.format(
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

            if len(masternodes_to_find) == 0 and len(delegates_to_find) == 0:
                break

        # At this point, start the discovery server if it's not already running because you are a masternode.

        #if not self.discovery_server.running:
        #    asyncio.ensure_future(
        #        self.discovery_server.serve()
        #    )

        self.log.success('Quorum reached! Begin protocol services...')

        return results

    def updated_peers_and_crawl(self, node_results, all_nodes, current_quorum):
        nodes = {}

        # Pack successful requests into a dictionary
        for node in node_results:
            if node is not None:
                nodes.update(node)

        # Update the peer table with the _new nodes
        self.log.info(nodes)
        self.peer_service.table.update(nodes)

        self.log.info(f'Peer table now: {self.peer_service.table}')

        # Remove the nodes from the all_nodes list. Don't need to query them again
        for vk, _ in nodes.items():
            try:
                all_nodes.remove(vk)
            except:
                pass

        # Return the number of nodes needed left
        return current_quorum - len(nodes)

    # Returns raw IP string for a node: 127.0.0.1 etc. Transform this into whatever you want.
    async def find_node(self, client_address: struct.SocketStruct =None, vk_to_find=None, retries=3):
        # Search locally if this is the case
        if str(client_address) == str(self.peer_service_address) or \
                vk_to_find == self.wallet.verifying_key().hex() or \
                client_address is None:

            response = {vk_to_find: self.peer_service.table.get(vk_to_find)} if self.peer_service.table.get(vk_to_find) is not None else self.peer_service.table

        # Otherwise, send out a network request
        else:
            find_message = ['find', vk_to_find]
            find_message = json.dumps(find_message, cls=struct.SocketEncoder).encode()
            response = await services.get(client_address, msg=find_message, ctx=self.ctx, timeout=1000)

            join_message = ['join', (self.wallet.verifying_key().hex(), self.socket_base)]
            join_msg = json.dumps(join_message).encode()
            asyncio.ensure_future(services.get(client_address, msg=join_msg, ctx=self.ctx, timeout=1000))

            if response is None:
                return None

            response = json.loads(response.decode())

        if response.get(vk_to_find) is not None:
            return response

        if retries <= 1:
            return None

        # Recursive crawl goes 'retries' levels deep
        for vk, ip in response.items():
            return await self.find_node(
                self.params.resolve(ip, ServiceType.PEER), vk_to_find, retries=retries - 1
            )

    def stop(self):
        self.peer_service.stop()

    def peers(self):
        return self.peer_service.table
