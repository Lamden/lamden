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

        self.vk = vk
        self.loop = loop or asyncio.get_event_loop()
        self.ctx = ctx or zmq.asyncio.Context()

        # raghu todo
        # self.event_socket?
        # self.server_socket?
        # data structure for req
        # replies don't save state - immediately process and reply - make sure they are light weight

        self.host_ip = HOST_IP
        self.port = DHT_PORT

        self.node = Node(digest(vk), ip=self.host_ip, port=self.port, vk=vk)

        self.identity = '{}:{}:{}'.format(self.host_ip, self.port, self.vk).encode()
        self.rep = None

        self.router_rep

        self.track_on = False     # do we need these ? raghu todo
        self.is_connected = False
        self.state_fname = '{}-network-state.dat'.format(os.getenv('HOST_NAME', 'node'))

        self.pending_replies = set()

        self.routing_table = RoutingTable(self, node)
        self.discovery = Discovery(vk, self.loop, self.ctx)

        self.tasks = [
            self.discovery.listen(),
            self.process_requests(),
            self.bootup()
        ]

    # raghu todo - do we need asyncio.gather here? don't think so
    def start(self):
        self.loop.run_until_complete(asyncio.gather(
            *self.tasks
        ))

    def stop(self):
        self.tasks.cancel()

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
        await self.rpc_lookup_node(event_id, nodes, vk_to_find)


    async def rpc_lookup_node(self, event_id, nodes_to_ask, vk_to_find):
        # raghu todo crp
        # open router socket and set proper options
        # while one more node to ask or one req pending
        # poll if any answer is available, if so, process it.
        # otherwise, send one more request
        # close socket and return answer

        req = self.ctx.socket(zmq.ROUTER)
        identity = "os.{}.{}".format(self.vk, event_id)
        req.setsockopt(zmq.IDENTITY, identity.encode())
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
                    nodes = self.rpc_reply(msg)
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
                await self.rpc_request(req, event_id, node, 'local_lookup_node', vk_to_find)
                num_pending_replies += 1
            else:
                await asyncio.sleep(1)    # sleep for 1 sec

        req.close()    # clean up socket
        return req_ip


    async def process_requests(self):
        """
        Start listening on the given port.

        Provide interface="::" to accept ipv6 address
        """
        self.rep = self.ctx.socket(zmq.ROUTER)
        self.rep.setsockopt(zmq.IDENTITY, self.identity)
        self.rep.setsockopt(zmq.LINGER, 10)           # ms
        self.rep.setsockopt(zmq.ROUTER_HANDOVER, 1)
        self.rep.bind('tcp://*:{}'.format(self.port))
        self.log.debug("Server {} listening on port {}".format(self.vk, self.port))
        while True:
            request = await self.rep.recv_multipart()
            addr = request[0].decode().split(':')
            data = request[1]
            await self.datagram_received(data, addr)

    async def datagram_received(self, datagram, address):
        log.spam("received datagram data {} from addr {}".format(datagram, address))
        if len(datagram) < 22:
            log.warning("received datagram too small from %s,"
                        " ignoring", address)
            return

        msgID = datagram[1:21]
        data = umsgpack.unpackb(datagram[21:])

        if datagram[:1] == b'\x00':
            # schedule accepting request and returning the result
            await self._acceptRequest(msgID, data, address)
        elif datagram[:1] == b'\x01':
            return self._acceptResponse(msgID, data, address)
        else:
            # otherwise, don't know the format, don't do anything
            log.spam("Received unknown message from %s, ignoring", address)

    def _acceptResponse(self, msgID, data, address):
        msgargs = (b64encode(msgID), address)
        log.spam("received response %s for message "
                  "id %s from %s", data, msgID, address)
        return data

    # raghu - need more protection against DOS?? like known string encrypted with its vk?
    async def _acceptRequest(self, msgID, data, address):
        if not isinstance(data, list) or len(data) != 2:
            raise MalformedMessage("Could not read packet: %s" % data)
        funcname, args = data
        log.spam("accepting request from {} to run {} with args {}".format(address, funcname, data))
        if funcname is None or not callable(funcname):
            msgargs = (self.__class__.__name__, funcname)
            log.warning("{} has no callable method {}; ignoring request".format(*msgargs))
            return

        if not asyncio.iscoroutinefunction(funcname):
            funcname = asyncio.coroutine(funcname)
        response = await funcname(address, *args)
        log.spam("sending response {} for msg id {} to {}".format(response, msgID, address))
        txdata = b'\x01' + msgID + umsgpack.packb(response)
        identity = '{}:{}:{}'.format(address[0], address[1], address[2]).encode()
        self.sock.send_multipart([identity, txdata])


# find_ip
#   - local_find_ip -> searches routing table and returns
#   - not there, do remote local_find_ip on each of the results
#   - when found, return and delete the entry ?  need lock mechanism


    def set_track_on(self):
        self.track_on = True

    def rpc_ping(self, sender, nodeid):
        source = Node(nodeid, sender[0], sender[1], sender[2])
        self.welcomeIfNewNode(source)
        return self.sourceNode.id

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

    async def callFindNode(self, nodeToAsk, nodeToFind, updateRoutingTable = True):
        address = (nodeToAsk.ip, nodeToAsk.port, self.sourceNode.vk)
        result = await self.find_node(address, self.sourceNode.id,
                                      nodeToFind.vk)
        return self.handleCallResponse(result, nodeToAsk, updateRoutingTable)

    async def callPing(self, nodeToAsk):
        # address = (nodeToAsk.ip, nodeToAsk.port, self.sourceNode.vk)
        # result = await self.ping(address, self.sourceNode.id)
        # return self.handleCallResponse(result, nodeToAsk)
        pass

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

    def handleCallResponse(self, result, node, updateRoutingTable):
        """
        If we get a response, add the node to the routing table.  If
        we get no response, make sure it's removed from the routing table.
        """
        nodes = []
        if not result[0]:
            log.warning("no response from %s, removing from router", node)
            self.router.removeContact(node)
            return nodes

        log.spam("got successful response from {} and response {}".format(node, result))
        self.welcomeIfNewNode(node)
        for t in result[1]:
            n = Node(digest(t[3]), ip=t[1], port=t[2], vk=t[3])
            if updateRoutingTable:
                self.welcomeIfNewNode(n)
            nodes.append(n)
        return nodes
-------------------------------------


    # debug only method
    def get_neighbors(self, vk=None):
        """
        return a list of neighbors for the given vk
        """

        neighbors = self.protocol.router.findNeighbors(vk if vk else self.node)
        return [tuple(n)[1:] for n in neighbors]

    def track_and_inform(self):
        self.protocol.set_track_on()

    async def lookup_ip(self, vk):
        try:
            return await asyncio.wait_for(self._lookup_ip(vk), FIND_NODE_TIMEOUT)
        except asyncio.TimeoutError:
            log.warning("Lookup IP exceeded timeout of {} for VK {}".format(FIND_NODE_TIMEOUT, vk))
            return None

    async def _lookup_ip(self, vk):
        log.spam('Attempting to look up node with vk="{}"'.format(vk))
        # node_to_find = Node(digest(vk), vk=vk)
        nearest = self.local_lookup_node(vk_to_find)
        nd = self.get_node_from_nodes_list(vk, nearest)
        if nd:
            log.debug('"{}" found in routing table resolving to {}'.format(vk, nd.ip))
            return nd.ip
        ip = await rpc_lookup_ip(self, nearest, vk)
        return ip

    async def _find_node(self, node, node_to_find):
        try:
            fut = asyncio.ensure_future(self.protocol.callFindNode(node, node_to_find))
            await asyncio.wait_for(fut, 12)
            return fut.result()
        except asyncio.TimeoutError:
            log.warning("find_node timed out asking node {} for node_to_find {}".format(node, node_to_find))

    async def local_lookup_node(self, vk_to_find):
        return self.protocol.router.findNode(Node(digest(vk_to_find), vk=vk_to_find))

    # async def rpc_lookup_ip(self, req, event_id, node_to_ask, vk_to_find):
    async def rpc_request(self, req, event_id, node_to_ask, name, *args):
        # add raddr to self.pending_replies  raghu todo

    async def rpc_reply(self, msg):
        raddr = msg[0]
        # raghu todo - welcomeNewNode?
        # remove raddr from self.pending_replies  raghu todo
        data = msg[1]
        # raghu todo error handling and audit layer ??
        assert data[:1] == b'\x01', "Expecting reply from remote node, but got something else!"
        return umsgpack.unpackb(data[1:])

    def get_node_from_nodes_list(self, vk, nodes):
        for node in nodes:
            if vk == node.vk:
                return node

