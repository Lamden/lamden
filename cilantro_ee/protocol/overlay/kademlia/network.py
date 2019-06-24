"""
Package for interacting on the network at a high level.
"""
import random
import pickle
import asyncio
import logging
import os
import time
import traceback
import uuid
import zmq, zmq.asyncio

from base64 import b64encode
from hashlib import sha1
import umsgpack

from cilantro_ee.protocol.overlay.kademlia.discovery import Discovery
from cilantro_ee.constants import conf
from cilantro_ee.protocol.overlay.kademlia.handshake import Handshake
from cilantro_ee.protocol.overlay.kademlia.node import Node
from cilantro_ee.protocol.overlay.kademlia.routing import RoutingTable
from cilantro_ee.protocol.overlay.kademlia.utils import digest
from cilantro_ee.protocol.overlay.kademlia.event import Event
from cilantro_ee.protocol.utils.socket import SocketUtil
from cilantro_ee.constants.ports import DHT_PORT
from cilantro_ee.constants.overlay_network import *
from cilantro_ee.logger.base import get_logger
from cilantro_ee.storage.vkbook import VKBook, PhoneBook

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

8. add update routing table functionality
9. complete authentication 
10. clean up
11. do singletons and clean up
12. hook up event socket part
13. test integration tests
     


    """

    def __init__(self, vk, ctx):

        self.loop = asyncio.get_event_loop()
        self.ctx = ctx

        self.log = get_logger('OS.Network')

        self.vk = vk
        self.host_ip = conf.HOST_IP
        self.port = DHT_PORT

        self.node = Node(digest(vk), ip=self.host_ip, port=self.port, vk=vk)

        self.rep = SocketUtil.create_socket(self.ctx, zmq.ROUTER)
        self.identity = '{}:{}:{}'.format(self.vk, self.host_ip, self.port).encode()
        self.rep.setsockopt(zmq.IDENTITY, self.identity)
        self.rep.bind('tcp://*:{}'.format(self.port))

        self.evt_sock = SocketUtil.create_socket(self.ctx, zmq.PUB)
        self.evt_sock.bind(EVENT_URL)
        Event.set_evt_sock(self.evt_sock)       # raghu todo - do we need this still as we have everything local

        self._use_ee_bootup = False             # turn this on for enterprise edition boot up method
        self.is_connected = False

        # raghu TODO - do we want to save routing table and use it as part of discovery process when rebooted ?? useful only in open discovery only - so punt for now
        # self.state_fname = '{}-network-state.dat'.format(os.getenv('HOST_NAME', 'node'))

        self.is_debug = False          # turn this on for verbose messages to debug
        self.busy_level = 0            # raghu TODO

        self.unheard_nodes = set()

        self.routing_table = RoutingTable(self.node)
        self.discovery = Discovery(vk, self.ctx)
        # self.handshake = Handshake(self.vk, self.ctx)

        self.tasks = [
            # self.handshake.listen(),
            # self.bootup(),
            self.process_requests()
        ]
        if not self._use_ee_bootup:
            self.tasks += [ self.discovery.listen() ]

    def start(self):
        self.loop.run_until_complete(asyncio.ensure_future(
            asyncio.gather(*self.tasks)
        ))

    def stop(self):
        self.teardown()

    def teardown(self):
        self.tasks.cancel()
        self.evt_sock.close()
        self.rep.close()

    # open source (public) version of booting up
    async def _bootup_os(self):
        addrs = await self.discovery.discover_nodes()
        if addrs:
            nodes = [Node(digest(addrs[ip]), ip=ip, port=self.port, vk=addrs[ip]) \
                           for ip in addrs ]
            await self.bootstrap(nodes)

    # enterprise version of booting up
    async def _bootup_ee(self):
        self.log.info("Loading vk, ip information of {} nodes in this enterprise setup".format(len(conf.VK_IP_MAP)))
        for vk, ip in conf.VK_IP_MAP.items():
            if vk == self.vk:     # no need to insert myself into the routing table
                continue
            node = Node(digest(vk), ip=ip, port=self.port, vk=vk)
            self.routing_table.addContact(node)
        await asyncio.sleep(5)

    async def _wait_for_boot_quorum(self):
        is_masternode = self.vk in PhoneBook.masternodes
        vks_to_wait_for = set()
        if is_masternode:
            quorum_required = PhoneBook.quorum_min
            quorum_required -= 1     # eliminate myself
            vk_list = PhoneBook.state_sync
            vk_list.remove(self.vk)
        else:
            quorum_required = PhoneBook.masternode_quorum_min
            vk_list = VKBook.masternodes

        if len(vk_list) < quorum_required:     # shouldn't happen
            self.log.fatal("Impossible to meet Quorum requirement as number of "
                           "nodes available {} is less than the quorum {}"
                           .format(len(vk_list), quorum_required))
            sys.exit()
            
        vks_to_wait_for.update(vk_list)
        vks_connected = self.routing_table.getAllConnectedVKs()
        vks_connected &= vks_to_wait_for
        # if len(vks_connected) >= quorum_required:     # already met the quorum
            # return
        vks_to_wait_for -= vks_connected
        while len(vks_to_wait_for) > 0:
            for vk in vks_to_wait_for:
                if await self._find_n_announce(vk):
                    vks_connected.add(vk)
            if len(vks_connected) >= quorum_required:
                return
            vks_to_wait_for -= vks_connected
            await asyncio.sleep(2)
     

    async def bootup(self):
        self.discovery.set_ready()
        if self._use_ee_bootup:
            await self._bootup_ee()
        else:
            await self._bootup_os()
        self.log.success('''
###########################################################################
#   BOOTSTRAP COMPLETE
###########################################################################\
        ''')
        await self._wait_for_boot_quorum()
        self.log.success('''
###########################################################################
#   MET BOOT QUORUM 
###########################################################################\
        ''')
        self.is_connected = True
        await Event.emit({'event': 'service_status', 'status': 'ready'})
        self.log.spam("Status ready sent!!!")

    async def bootstrap(self, nodes):
        """
        Bootstrap the server by connecting to other discovered nodes in the network
              by executing 'find me' on each of them

        Args:
            nodes: A list of nodes with the info (ip, port).  Note that only IP
                   addresses are acceptable - hostnames will cause an error.
        """

        if self.is_debug:
            self.log.debug("Attempting to bootstrap node with {} initial contacts: {}".format(len(nodes), nodes))
        event_id = uuid.uuid4().hex
        vk_to_find = self.vk         # me
        await self.network_find_ip(event_id, nodes, vk_to_find, True)

    async def process_requests(self):
        """
        Start listening on the given port.
        """

        if self.is_debug:
            self.log.debug("Server {} listening on port {}".format(self.vk, self.port))
        while True:
            try:
                request = await self.rep.recv_multipart()
                await self.process_msg_recvd(request)

            except zmq.ZMQError as e:
                self.log.warning("ZMQError '{}' in process_requests\n".format(e))
            except Exception as e:
                self.log.warning("Exception '{}' in process_requests".format(e))
        self.log.warning("Exiting listening for overlay requests!!")

    async def process_msg_recvd(self, msg):
        address = msg[0].decode().split(':')
        datagram = msg[1]
        if len(datagram) < 1:
            self.log.warning("Received datagram too small from {}, ignoring".format(address))
            return

        data = umsgpack.unpackb(datagram[1:])

        if self.is_debug:
            self.log.debug("Received message {} from addr {}".format(data, address))

        if datagram[:1] == b'\x00':
            # schedule accepting request and returning the result
            await self._acceptRequest(address, data)
        elif datagram[:1] == b'\x01':
            return self._acceptResponse(address, data)
        else:
            # otherwise, don't know the format, don't do anything
            self.log.warning("Received unknown message from {}, ignoring".format(address))

    def _acceptResponse(self, address, data):
        self.log.error("ERROR *** this shouldn't be entered")
        return data

    # raghu - need more protection against DOS?? like known string encrypted with its vk?
    async def _acceptRequest(self, address, data):
        if not isinstance(data, list) or len(data) != 2:
            raise MalformedMessage("Could not read packet: %s" % data)
        funcname, args = data
        func = getattr(self, funcname, None)
        if func is None or not callable(func):
            msgargs = (self.__class__.__name__, func)
            self.log.warning("{} has no callable method {}; ignoring request".format(*msgargs))
            return

        if not asyncio.iscoroutinefunction(func):
            func = asyncio.coroutine(func)
        response = await func(address, *args)
        txdata = b'\x01' + umsgpack.packb(response)
        identity = '{}:{}:{}'.format(address[0], address[1], address[2]).encode()
        try:
            await self.rep.send_multipart([identity, txdata])
            if self.is_debug:
                self.log.debug("sent response {} to {}".format(response, address))

        except zmq.ZMQError as e:
            self.log.warning("Got ZMQError when replying to msg from {}: {}".format(identity, e))
        except Exception as e:
            self.log.warning("Got exception when replying to msg from {}: {}".format(identity, e))

        rnode = Node(digest(address[0]), address[1], self.port, address[0])
        self.welcomeIfNewNode(rnode)


    def welcomeIfNewNode(self, node):
        """
        Given a new node, send it all the keys/values it should be storing,
        then add it to the routing table.

        @param node: A new node that just joined (or that we just found out
        about).

        """
        if not self.routing_table.isNewNode(node):
            return

        if self.is_debug:
            self.log.debug("never seen %s before, adding to routing_table", node)
        self.routing_table.addContact(node)


    def local_find_ip(self, vk_to_find):
        return self.routing_table.findNode(Node(digest(vk_to_find), vk=vk_to_find))

    async def rpc_find_ip(self, address, vk_to_find):
        if self.is_connected and address[0] == vk_to_find:
            await Event.emit({'event': 'node_online', 'vk': vk_to_find, 'ip': address[1]})
        nodes = self.local_find_ip(vk_to_find)
        return list(map(tuple, nodes))

    async def rpc_ping_ip(self, address, is_first_time):
        if is_first_time:
            self.log.debug("Got ping from {}:{}".format(address[0], address[1]))
            # publish to the event
        return True

    async def rpc_connect(self, req, vk, ip):
        raddr = '{}:{}:{}'.format(vk, ip, self.port).encode()
        req.connect('tcp://{}:{}'.format(ip, self.port))
        if self.is_debug:
            self.log.debug("Connected to {}".format(raddr))
        return raddr

    async def rpc_request(self, req, raddr, func_name, *args):
        self.unheard_nodes.add(raddr)
        data = umsgpack.packb([func_name, args])
        if len(data) > 8192:
            raise MalformedMessage("Total length of function name "
                                   "and arguments cannot exceed 8K")
        txdata = b'\x00' + data
        try:
            await req.send_multipart([raddr, txdata])
            if self.is_debug:
                self.log.debug("Sent the request to {}".format(raddr))
            return True

        except zmq.ZMQError as e:
            if self.is_debug or (e.errno != zmq.EHOSTUNREACH):
                self.log.warning("ZMQError in sending request to {}: {}".format(raddr, e))
        except Exception as e:
            self.log.warning("Got exception in sending request to {}: {}".format(raddr, e))

        return False

    def rpc_response(self, result):
        nodes = []
        for t in result:
            n = Node(digest(t[3]), ip=t[1], port=t[2], vk=t[3])
            nodes.append(n)
        return nodes
  
    def get_node_from_nodes_list(self, vk, nodes):
        for node in nodes:
            if vk == node.vk:
                return node

    async def try_rpc_response(self, req, pinterval):
        try:
            event = await req.poll(timeout=pinterval, flags=zmq.POLLIN)
            if event == zmq.POLLIN:
                msg = await req.recv_multipart(zmq.DONTWAIT)
                if msg[0] in self.unheard_nodes:
                    self.unheard_nodes.remove(msg[0])
                raddr = msg[0].decode()
                addr_list = raddr.split(':')
                rnode = Node(digest(addr_list[0]), addr_list[1], addr_list[2], addr_list[0])
                self.welcomeIfNewNode(rnode)
                data = msg[1]
                # raghu TODO error handling and audit layer ??
                assert data[:1] == b'\x01', "Expecting reply from remote node, but got something else!"
                result = umsgpack.unpackb(data[1:])
                if self.is_debug:
                    self.log.debug('Received {} from {}'.format(result, raddr))
                return result

        except Exception as e:
            self.log.warning("Exception '{}' in network_find_ip".format(e))

        return None

    async def _network_find_ip(self, req, nodes_to_ask, vk_to_find, is_bootstrap=False):
        processed = set()
        processed.add(self.vk)
        failed_requests = set()
        is_retry = True
        num_pending_replies = 0
        pinterval = 0
        is_done = False
        retry_time = time.time() + 3    # 3 seconds 
        end_time = time.time() + 6      # 6 seconds is max

        if self.is_debug:
            self.log.debug("Asking {} for the vk {}".format(nodes_to_ask, vk_to_find))
        while ((time.time() < end_time) and not is_done):
            # first poll and process any replies
            if self.is_debug:
                self.log.debug("Num pending requests {} Num pending replies {} Num Failed requests {}".format(len(nodes_to_ask), num_pending_replies, len(failed_requests)))
            if num_pending_replies > 0:
                msg = await self.try_rpc_response(req, pinterval)
                if msg:
                    nodes = self.rpc_response(msg)
                    # in bootstrap mode, shouldn't return prematurely
                    nd = None if is_bootstrap else \
                         self.get_node_from_nodes_list(vk_to_find, nodes)
                    if nd:
                        if self.is_debug:
                            self.log.debug('Found ip {} for vk {}'.format(nd.ip, nd.vk))
                        return nd
                    nodes_to_ask.extend(nodes)
                    num_pending_replies -= 1

            if len(nodes_to_ask) > 0:
                node = nodes_to_ask.pop()
                if node.vk in processed or \
                   (is_bootstrap and not self.routing_table.isNewNode(node)):
                    if self.is_debug:
                        self.log.debug('Already processed this vk {}'.format(node.vk))
                    continue
                if self.is_debug:
                    self.log.debug('Asking {}:{} about vk {}'.format(node.vk, node.ip, vk_to_find))
                processed.add(node.vk)
                raddr = await self.rpc_connect(req, node.vk, node.ip)
                is_sent = await self.rpc_request(req, raddr, 'rpc_find_ip', vk_to_find)
                if is_sent:
                    num_pending_replies += 1
                elif is_retry:
                    failed_requests.add(raddr)
            elif len(failed_requests) > 0:           # expectation is that this is only needed for tests
                ctime = time.time()
                if ctime < retry_time:
                    await asyncio.sleep(retry_time - ctime)
                # If we save failed requests along with original request time, re-request interval can be better controlled
                for raddr in failed_requests:
                    if self.is_debug:
                        self.log.debug('Requesting again {} about vk {}'.format(raddr, vk_to_find))
                    is_sent = await self.rpc_request(req, raddr, 'rpc_find_ip', vk_to_find)
                    if is_sent:
                        num_pending_replies += 1
                failed_requests.clear()
            elif num_pending_replies == 0:
                is_done = True
            else:     # increase poll time here
                pinterval = 1000

        return None

    async def network_find_ip(self, event_id, nodes_to_ask, vk_to_find, is_bootstrap=False):
        req = SocketUtil.create_socket(self.ctx, zmq.ROUTER)
        req.setsockopt(zmq.IDENTITY, '{}:{}:{}'.format(self.vk, self.host_ip, event_id).encode())
        node = await self._network_find_ip(req, nodes_to_ask, vk_to_find, is_bootstrap)
        req.close()    # clean up socket  # handle the errors on remote properly
        return node

    async def find_ip(self, event_id, vk_to_find):
        if self.is_debug:
            self.log.debug("find_ip called for vk {} with event_id {}".format(vk_to_find, event_id))
        nodes = self.local_find_ip(vk_to_find)
        nd = self.get_node_from_nodes_list(vk_to_find, nodes)
        if not nd:
            nd = await self.network_find_ip(event_id, nodes, vk_to_find)
        ip = nd.ip if nd else None
        # status = 'authorized' if ip else 'unknown_vk'
        # await Event.emit({'event': status, 'vk': vk_to_find, 'ip': ip, 'domain': '*'})
        return ip

    async def _find_n_announce(self, vk_to_find):
        event_id = uuid.uuid4().hex
        req = SocketUtil.create_socket(self.ctx, zmq.ROUTER)
        req.setsockopt(zmq.IDENTITY, '{}:{}:{}'.format(self.vk, self.host_ip, event_id).encode())
        nodes_to_ask = self.local_find_ip(vk_to_find)
        node = await self._network_find_ip(req, nodes_to_ask, vk_to_find, False)
        if node:          # found it, now announce myself
            await self._network_find_ip(req, [node], self.vk, False)
            status = True
        else:
            status = False
        req.close()    # clean up socket  # handle the errors on remote properly
        return node

    async def _ping_ip(self, req, vk, ip, is_first_time):
        raddr = await self.rpc_connect(req, vk, ip)
        is_sent = await self.rpc_request(req, raddr, 'rpc_ping_ip', is_first_time)
        if not is_sent:
            return False
        result = await self.try_rpc_response(req, 3000)     # wait for 3 sec max
        return True if result else False

    async def ping_ip(self, event_id, vk, ip, is_first_time):
        req = SocketUtil.create_socket(self.ctx, zmq.ROUTER)
        req.setsockopt(zmq.IDENTITY, '{}:{}:{}'.format(self.vk, self.host_ip, event_id).encode())
        status = await self._ping_ip(req, vk, ip, is_first_time)
        req.close()    # clean up socket  # handle the errors on remote properly
        return status

    async def find_ip_and_authenticate(self, event_id, vk_to_find, is_first_time):
        if self.is_debug:
            self.log.debug("find_ip_and_authenticate called for vk {} with event_id {}".format(vk_to_find, event_id))
        ip = self.find_ip(event_id, vk_to_find)
        is_auth = False
        if ip:
            # raghu TODO if is_first_time, announce it as node_on_line - that is on the other side
            # is_auth = await self.handshake.authenticate(event_id, vk_to_find, ip, domain, is_first_time)
            is_auth = await self.ping_ip(event_id, vk_to_find, ip, is_first_time)
        return ip, is_auth


