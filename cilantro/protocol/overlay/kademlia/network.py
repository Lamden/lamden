"""
Package for interacting on the network at a high level.
"""
import random
import pickle
import asyncio
import logging
import os
import uuid
import zmq, zmq.asyncio

from base64 import b64encode
from hashlib import sha1
import umsgpack

from cilantro.protocol.overlay.kademlia.node import Node
from cilantro.protocol.overlay.kademlia.routing import RoutingTable
from cilantro.protocol.overlay.kademlia.utils import digest
from cilantro.protocol.overlay.event import Event
from cilantro.constants.ports import DHT_PORT
from cilantro.constants.overlay_network import *
from cilantro.logger.base import get_logger

log = get_logger(__name__)

class MalformedMessage(Exception):
    """
    Message does not contain what is expected.
    """

class Network(object):
    """
    Implementation of Overlay Server. This connects to the other nodes on the network
    and services the client requests
    
1. two sockets dealer and router.
2. open dealer socket and provide listen function
3. router socket will be opened, bound only after bootstrap is done 
      make sure the case where two masters got each other as the initial contacts work here
      perhaps router socket can be opened and listened to if it is a master node?
      - needs to tie with listen on discovery channel ?
4. raghu - todo - directory reset (part of auth)
                - secure socket routines?
                - do we need ksize, alpha and node in network or can they be pushed to routing_table, etc?

5. control flow:
     - initialization including dir resets etc
     - all task creation and start
6. functional flow:
     - server sockets 
     - network sockets available (? should be available as it may be hard to synchronize)
     - discovery - only discovery sockets are active, not any other sockets in network, etc
     - bootstrap  - findMe
     - server available for service

     - handshake - all listen functions will set or increment the counter that triggers main processing ?

7. move event socket into network itself
     


    """

    def __init__(self, vk, loop=None, ctx=None):

        self.loop = loop or asyncio.get_event_loop()
        self.ctx = ctx or zmq.asyncio.Context()

        # raghu todo
        # self.event_socket?
        # self.server_socket?
        # data structure for req
        # replies don't save state - immediately process and reply - make sure they are light weight

        self.vk = vk
        self.host_ip = HOST_IP
        self.port = DHT_PORT

        self.node = Node(digest(vk), ip=self.host_ip, port=self.port, vk=vk)

        # raghu todo - change this to vk, ip, port order and for temp ones, use event_id for port
        self.identity = '{}:{}:{}'.format(self.vk, self.host_ip, self.port).encode()
        self.rep = self.ctx.socket(zmq.ROUTER)
        self.rep.setsockopt(zmq.IDENTITY, self.identity)
        self.rep.setsockopt(zmq.LINGER, 10)           # ms
        self.rep.setsockopt(zmq.ROUTER_HANDOVER, 1)
        self.rep.bind('tcp://*:{}'.format(self.port))

        self.evt_sock = self.ctx.socket(zmq.PUB)
        self.evt_sock.bind(EVENT_URL)
        Event.set_evt_sock(self.evt_sock)       # raghu todo - do we need this still as we have everything local

        self.track_on = False     # do we need these ? raghu todo
        self.is_connected = False
        self.state_fname = '{}-network-state.dat'.format(os.getenv('HOST_NAME', 'node'))

        self.pending_replies = set()

        # raghu todo - pass vk, host_ip, port to routing_table
        self.routing_table = RoutingTable(self, node)
        self.discovery = Discovery(vk, self.loop, self.ctx)

        self.tasks = [
            self.discovery.listen(),
            self.process_requests(),
            self.bootup()
        ]

    # raghu todo - do we need asyncio.gather here? don't think so
    def run(self):
        self.loop.run_until_complete(asyncio.gather(
            *self.tasks
        ))

    def stop(self):
        self.teardown()

    def teardown(self):
        self.tasks.cancel()
        self.evt_sock.close()
        self.rep.close()

    async def bootup(self):
        addrs = await self.discovery.discover_nodes()
        if addrs:
            # raghu todo - eliminate self.vk being part of addrs and eliminate the if below
            nodes = [Node(digest(vk), ip=addrs[vk], port=self.port, vk=vk) \
                                     for vk in addrs if vk is not self.vk]
            await self.bootstrap(nodes)
        self.log.success('''
###########################################################################
#   BOOTSTRAP COMPLETE
###########################################################################\
        ''')
        self.is_connected = True
        Event.emit({ 'event': 'service_status', 'status': 'ready' })

    async def bootstrap(self, nodes):
        """
        Bootstrap the server by connecting to other discovered nodes in the network
              by executing 'find me' on each of them

        Args:
            nodes: A list of nodes with the info (ip, port).  Note that only IP
                   addresses are acceptable - hostnames will cause an error.
        """

        log.debug("Attempting to bootstrap node with {} initial contacts: {}".format(len(nodes), nodes))
        event_id = uuid.uuid4().hex
        vk_to_find = self.vk         # me
        await self.network_lookup_node(event_id, nodes, vk_to_find)


    async def process_requests(self):
        """
        Start listening on the given port.
        """

        self.log.debug("Server {} listening on port {}".format(self.vk, self.port))
        while True:
            request = await self.rep.recv_multipart()
            await self.process_msg_recvd(request)

    async def process_msg_recvd(self, msg):
        address = msg[0].decode().split(':')
        datagram = msg[1]
        if len(datagram) < 1:
            log.warning("Received datagram too small from {}, ignoring".format(address))
            return

        # msgID = datagram[1:21]
        data = umsgpack.unpackb(datagram[1:])

        log.spam("Received message {} from addr {}".format(data, address))

        if datagram[:1] == b'\x00':
            # schedule accepting request and returning the result
            await self._acceptRequest(address, data)
        elif datagram[:1] == b'\x01':
            return self._acceptResponse(address, data)
        else:
            # otherwise, don't know the format, don't do anything
            log.spam("Received unknown message from {}, ignoring".format(address))

    def _acceptResponse(self, address, data):
        log.important("ERROR *** this shouldn't be entered")
        # raghu todo - pass address to emit the event, but do the welcomeIfNewNode here
        return data

    # raghu - need more protection against DOS?? like known string encrypted with its vk?
    async def _acceptRequest(self, address, data):
        if not isinstance(data, list) or len(data) != 2:
            raise MalformedMessage("Could not read packet: %s" % data)
        funcname, args = data
        if funcname is None or not callable(funcname):
            msgargs = (self.__class__.__name__, funcname)
            log.warning("{} has no callable method {}; ignoring request".format(*msgargs))
            return

        if not asyncio.iscoroutinefunction(funcname):
            funcname = asyncio.coroutine(funcname)
        response = await funcname(address, *args)
        txdata = b'\x01' + umsgpack.packb(response)
        identity = '{}:{}:{}'.format(address[0], address[1], address[2]).encode()
        self.sock.send_multipart([identity, txdata])
        log.spam("sent response {} to {}".format(response, address))
        # raghu todo - pass address to emit the event, but do the welcomeIfNewNode here


    def set_track_on(self):
        self.track_on = True


    def rpc_find_node(self, sender, nodeid, key):
        log.debugv("finding neighbors of {} in local table for {}".format(key, sender))
        source = Node(nodeid, sender[0], sender[1], sender[2])

        # DEBUG -- TODO DELETE
        # log.important2("Got find_node req from sender with vk {}, who is looking for {}.\nself.track_on={}\nself.router"
        #                ".isNewNode(source)={}".format(sender[2], key, self.track_on, self.router.isNewNode(source)))
        # END DEBUG

        # NOTE: we are always emitting node_online when we get a find_node request, because we don't know when clients
        # drop. A client could drop, but still be in our routing table because we don't heartbeat. Always sending
        # 'node_online' might be a heavy handed solution, but under the assumption that find_nodes (vk lookups) are
        # a relatively infrequent operation, this should be acceptable  --davis
        emit_to_client = self.track_on  #  and self.router.isNewNode(source)
        self.welcomeIfNewNode(source)
        if emit_to_client:
            Event.emit({'event': 'node_online', 'vk': source.vk, 'ip': source.ip})
        node = Node(digest(key))
        neighbors = self.router.findNode(node)
        return list(map(tuple, neighbors))


    # debug only method
    def get_neighbors(self, vk=None):
        """
        return a list of neighbors for the given vk
        """

        neighbors = self.protocol.router.findNeighbors(vk if vk else self.node)
        return [tuple(n)[1:] for n in neighbors]


    def welcomeIfNewNode(self, node):
        """
        Given a new node, send it all the keys/values it should be storing,
        then add it to the routing table.

        @param node: A new node that just joined (or that we just found out
        about).

        """
        if not self.router.isNewNode(node):
            return

        log.debug("never seen %s before, adding to router", node)
        self.router.addContact(node)


    def local_find_ip(self, vk_to_find):
        return self.router.findNode(Node(digest(vk_to_find), vk=vk_to_find))

    async def rpc_find_ip(self, address, vk_to_find):
        rnode = Node(digest(address[0]), address[1], self.port, address[0])
        self.welcomeIfNewNode(rnode)
        if address[0] == vk_to_find:
            // bootstrapping - raghu todo - not enough - even findNode has to have a way 
            // better still - have a function to (new) ping to every one it needs to connect or it needs to connect to you
            Event.emit({'event': 'node_online', 'vk': source.vk, 'ip': source.ip})
        return self.local_lookup_node(vk_to_find)

    # async def rpc_lookup_ip(self, req, event_id, node_to_ask, vk_to_find):
    # don't need to transmit event_id as it is part of the identity
    async def rpc_request(self, req, node_to_ask, func_name, *args):
        # add raddr to self.pending_replies  raghu todo
        req.connect('tcp://{}:{}'.format(node_to_ask.ip, node_to_ask.port))
        raddr = '{}:{}:{}'.format(node_to_ask.vk, node_to_ask.ip, self.port).encode()
        self.pending_replies.add(raddr)
        data = umsgpack.packb([func_name, args])
        if len(data) > 8192:
            raise MalformedMessage("Total length of function name "
                                   "and arguments cannot exceed 8K")
        txdata = b'\x00' + data
        sock.send_multipart([raddr, txdata])


    async def rpc_response(self, msg):
        raddr = msg[0].decode()
        if raddr in self.pending_replies:
            self.pending_replies.remove(raddr)
        # raghu todo - welcomeNewNode?
        addr_list = raddr.split(':')
        rnode = Node(digest(addr_list[0]), addr_list[1], addr_list[2], addr_list[0])
        self.welcomeIfNewNode(rnode)
        data = msg[1]
        # raghu todo error handling and audit layer ??
        assert data[:1] == b'\x01', "Expecting reply from remote node, but got something else!"
        # msgID = datagram[1:21]
        # data = umsgpack.unpackb(datagram[21:])
        # raghu todo - we need to standarize whether eventId would be part of arguments or the extra one and be consistent
        # raghu replies don't need to include event_ids?
        return umsgpack.unpackb(data[1:])

    def get_node_from_nodes_list(self, vk, nodes):
        for node in nodes:
            if vk == node.vk:
                return node

    async def network_find_ip(self, event_id, nodes_to_ask, vk_to_find):
        # raghu todo crp
        # open router socket and set proper options
        # while one more node to ask or one req pending
        # poll if any answer is available, if so, process it.
        # otherwise, send one more request
        # close socket and return answer

        req = self.ctx.socket(zmq.ROUTER)
        req.setsockopt(zmq.IDENTITY, '{}:{}:{}'.format(self.vk, self.host_ip, event_id).encode())
        req.setsockopt(zmq.LINGER, 100)
        req.setsockopt(zmq.RCVTIMEO, 1000)    # do we still need it with polling
        req.setsockopt(zmq.SNDTIMEO, 100)

        poller = zmq.Poller()
        poller.register(req, zmq.POLLIN)
        processed = set(self.vk)
        num_pending_replies = 0
        req_ip = None

        while (len(nodes_to_ask) > 0) or (num_pending_replies > 0):
            # raghu todo - need to check if polling without connecting to anyone will have issues
            # first poll and process any replies
            if num_pending_replies > 0:
                socks = dict(poller.poll())
                if req in socks and socks[req] == zmq.POLLIN:
                    msg = await req.recv_multipart()
                    num_pending_replies -= 1
                    # raghu todo - this has eventId now - won't work as is
                    nodes = self.rpc_response(msg)
                    nd = self.get_node_from_nodes_list(vk_to_find, nodes)
                    if nd:
                        log.debug('Got ip {} for vk {} from {}'.format(nd.ip, nd.vk, addr))
                        req_ip = nd.ip
                        break
                    nodes_to_ask.update(nodes)
                    continue
            if len(nodes_to_ask) > 0:
                node = nodes_to_ask.pop()
                if node.vk in processed:
                    continue
                processed.add(node.vk)
                await self.rpc_request(req, node, 'rpc_lookup_node', vk_to_find)
                num_pending_replies += 1
            else:
                await asyncio.sleep(1)    # sleep for 1 sec

        req.close()    # clean up socket  # handle the errors on remote properly
        return req_ip


    async def find_ip(self, event_id, vk_to_find):
        self.log.debug("find_ip called for vk {} with event_id {}".format(vk_to_find, event_id))
        nodes = self.local_find_ip(vk_to_find)
        nd = self.get_node_from_nodes_list(vk_to_find, nodes)
        if nd:
            return nd.ip
        return await self.network_find_ip(event_id, nodes, vk_to_find)


    async def authenticate(self, event_id, is_first_time, ip, domain):

