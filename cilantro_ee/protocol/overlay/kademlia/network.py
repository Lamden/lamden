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
from cilantro_ee.constants.ports import DISCOVERY_PORT
from cilantro_ee.constants.overlay_network import PEPPER
from cilantro_ee.protocol.overlay.kademlia.discovery import DiscoveryServer, discover_nodes
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
    pass

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

    def __init__(self, wallet, ctx):

        self.loop = asyncio.get_event_loop()
        self.ctx = ctx

        self.log = get_logger('OS.Network')

        self.wallet = wallet

        self.vk = self.wallet.verifying_key().hex()

        self.host_ip = conf.HOST_IP
        self.port = DHT_PORT

        self.node = Node(digest(self.vk), ip=self.host_ip, port=self.port, vk=self.vk)

        self.rep = self.generate_router_socket(self.port)
        self.rep.bind('tcp://*:{}'.format(self.port))

        self.evt_sock = SocketUtil.create_socket(self.ctx, zmq.PUB)
        self.evt_sock.bind(EVENT_URL)
        Event.set_evt_sock(self.evt_sock)       # raghu todo - do we need this still as we have everything local

        self._use_ee_bootup = False             # turn this on for enterprise edition boot up method
        self.is_connected = False

        self.is_debug = False          # turn this on for verbose messages to debug
        self.busy_level = 0            # raghu TODO

        self.unheard_nodes = set()

        self.routing_table = RoutingTable(self.node)

        self.log.info('Setting up Discovery Server.')
        self.discovery_server = DiscoveryServer(ip='*',
                                                port=DISCOVERY_PORT,
                                                wallet=self.wallet,
                                                pepper=PEPPER.encode(),
                                                ctx=self.ctx)

        self.tasks = [
            self.process_requests(),
            self.bootup()
        ]
        if not self._use_ee_bootup:
            if self.vk in PhoneBook.masternodes:
                print('I should run a server.')
                self.tasks += [self.discovery_server.serve()]

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
        self.discovery_server.stop()

    def tcp_string_to_ip(self, t):
        ip = t.lstrip('tcp://')
        ip = ip.split(':')[0]
        return ip

    # open source (public) version of booting up
    async def _bootup_os(self):
        self.log.success('BOOTUP TIME OS')
        ip_list = conf.BOOTNODES

        # Remove our own IP so that we don't respond to ourselves.
        if conf.HOST_IP in ip_list:
            ip_list.remove(conf.HOST_IP)

        self.log.info('Pinging {} for discovery...'.format(ip_list))

        ip_list = ['tcp://{}:{}'.format(ip, DISCOVERY_PORT) for ip in ip_list]

        addrs = await discover_nodes(ip_list, pepper=PEPPER.encode(), ctx=self.ctx)

        self.log.info(addrs)

        if len(addrs):
            self.log.success('Found {} node(s). Putting them in the DHT.'.format(len(addrs)))

            nodes = [Node(digest(vk), ip=self.tcp_string_to_ip(ip), port=self.port, vk=vk) for ip, vk in addrs.items()]

            if not self.discovery_server.running:
                self.log.info('Discovery server was not running. Starting it now so others can find us.')
                asyncio.ensure_future(self.discovery_server.serve())

            self.log.success('Going into bootstrap!')
            await self.bootstrap(nodes)

        else:
            raise Exception('Failed to discover any nodes.')

    # enterprise version of booting up
    async def _bootup_ee(self):
        self.log.info("Loading vk, ip information of {} nodes in this enterprise setup".format(len(conf.VK_IP_MAP)))

        for vk, ip in conf.VK_IP_MAP.items():
            if vk == self.vk:     # no need to insert myself into the routing table
                continue
            node = Node(digest(vk), ip=ip, port=self.port, vk=vk)
            self.routing_table.add_contact(node)
        await asyncio.sleep(5)

    async def _wait_for_boot_quorum(self):
        self.log.info('Time to find the quorum.')
        is_masternode = self.vk in PhoneBook.masternodes
        vks_to_wait_for = set()

        if is_masternode:
            quorum_required = PhoneBook.quorum_min
            quorum_required -= 1     # eliminate myself
            vk_list = PhoneBook.state_sync
            vk_list.remove(self.vk)
            self.log.info('Needs to find {} nodes.'.format(quorum_required))
        else:
            quorum_required = PhoneBook.masternode_quorum_min
            vk_list = PhoneBook.masternodes

            
        vks_to_wait_for.update(vk_list)
        vks_connected = self.routing_table.all_nodes()
        vks_connected &= vks_to_wait_for

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
        #self.discovery.set_ready()
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
        self.log.info("Attempting to bootstrap node with {} initial contacts: {}".format(len(nodes), nodes))
        event_id = uuid.uuid4().hex
        vk_to_find = self.vk         # me
        await self.network_find_ip(event_id, nodes, vk_to_find, True)

    async def process_requests(self):
        # Find IP? Is this all?
        """
        Start listening on the given port.
        """

        self.log.info("Server {} listening on port {}".format(self.vk, self.port))
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
        # msg is a list
        address = msg[0].decode().split(':') # Sender's identity
        datagram = msg[1] # Rest of the message as bytes


        if len(datagram) < 1:
            self.log.warning("Received datagram too small from {}, ignoring".format(address))
            return

        data = umsgpack.unpackb(datagram[1:])

        self.log.info("Received message {} from addr {}".format(data, address))

        if datagram[:1] == b'\x00':
            # schedule accepting request and returning the result
            await self._acceptRequest(address, data)
        else:
            self.log.warning("Received unknown message from {}, ignoring".format(address))

    # raghu - need more protection against DOS?? like known string encrypted with its vk?
    async def _acceptRequest(self, address, data):
        # rpc_findip
        #
        if not isinstance(data, list) or len(data) != 2:
            raise MalformedMessage("Could not read packet: %s" % data)

        # Change this from dynamic deserialization into static function calls.
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

        # VK, IP, event IP
        identity = '{}:{}:{}'.format(address[0], address[1], address[2]).encode()

        try:
            await self.rep.send_multipart([identity, txdata])
            self.log.info("sent response {} to {}".format(response, address))

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
        if not self.routing_table.is_new_node(node):
            return

        self.log.info("never seen %s before, adding to routing_table", node)
        self.routing_table.add_contact(node)

    # supported command!
    # address = sender identity 127.0.0.1:ID:BLAH
    # [VK, IP] = address
    # vk is 32 bytes / hex string
    async def rpc_find_ip(self, address, vk_to_find):
        # when new node joins, it send a search request for itself to tell the network it has joined
        # can be its own command, probably
        if self.is_connected and address[0] == vk_to_find:
            await Event.emit({'event': 'node_online', 'vk': vk_to_find, 'ip': address[1]})

        # find neighbors and return them
        # reciever can only tell node which neighbors it knows the new node should have based on
        # its own neighbors
        nodes = self.routing_table.find_node(Node(digest(vk_to_find), vk=vk_to_find))
        return list(map(tuple, nodes))

    # supported command!

    async def rpc_ping_ip(self, address, is_first_time):
        if is_first_time:
            self.log.info("Got ping from {}:{}".format(address[0], address[1]))
            # publish to the event
        return True

    # INTERNAL. Will not be called by RPC request (so prevent it from happening for sec?)
    async def rpc_request(self, req, raddr, func_name, *args):
        self.unheard_nodes.add(raddr)
        data = umsgpack.packb([func_name, args])
        if len(data) > 8192:
            raise MalformedMessage("Total length of function name "
                                   "and arguments cannot exceed 8K")
        txdata = b'\x00' + data
        try:
            await req.send_multipart([raddr, txdata])
            self.log.info("Sent the request to {}".format(raddr))
            return True

        except zmq.ZMQError as e:
            self.log.warning("ZMQError in sending request to {}: {}".format(raddr, e))
        except Exception as e:
            self.log.warning("Got exception in sending request to {}: {}".format(raddr, e))

        return False

    async def new_rpc_request(self, socket, identity, ip: str, sender_vk: bytes, requested_vk: bytes):
        ip_ints = [int(i) for i in ip.split('.')]
        ip_bytes = bytes(ip_ints)

        msg = ip_bytes + sender_vk + requested_vk


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
                self.log.info('Received {} from {}'.format(result, raddr))
                return result

        except Exception as e:
            self.log.warning("Exception '{}' in network_find_ip".format(e))

        return None

    async def _network_find_ip(self, req, nodes_to_ask, vk_to_find, is_bootstrap=False):
        self.log.info('SOCKET IS THIS: {}'.format(req))

        processed = set()
        processed.add(self.vk)
        failed_requests = set()
        is_retry = True
        num_pending_replies = 0
        pinterval = 0
        is_done = False
        retry_time = time.time() + 3    # 3 seconds
        end_time = time.time() + 6      # 6 seconds is max

        self.log.info("Asking {} for the vk {}".format(nodes_to_ask, vk_to_find))
        while ((time.time() < end_time) and not is_done):
            # first poll and process any replies
            self.log.info("Num pending requests {} Num pending replies {} Num Failed requests {}".format(len(nodes_to_ask), num_pending_replies, len(failed_requests)))
            if num_pending_replies > 0:
                msg = await self.try_rpc_response(req, pinterval)
                if msg:
                    nodes = self.rpc_response(msg)
                    # in bootstrap mode, shouldn't return prematurely
                    nd = None if is_bootstrap else \
                         self.get_node_from_nodes_list(vk_to_find, nodes)
                    if nd:
                        self.log.info('Found ip {} for vk {}'.format(nd.ip, nd.vk))
                        return nd
                    nodes_to_ask.extend(nodes)
                    num_pending_replies -= 1

            if len(nodes_to_ask) > 0:
                node = nodes_to_ask.pop()
                if node.vk in processed or \
                   (is_bootstrap and not self.routing_table.is_new_node(node)):
                    self.log.info('Already processed this vk {}'.format(node.vk))
                    continue
                self.log.info('Asking {}:{} about vk {}'.format(node.vk, node.ip, vk_to_find))
                processed.add(node.vk)

                raddr = '{}:{}:{}'.format(node.vk, node.ip, self.port).encode()
                overlay_address = 'tcp://{}:{}'.format(node.ip, self.port)
                req.connect(overlay_address)

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
                    self.log.info('Requesting again {} about vk {}'.format(raddr, vk_to_find))
                    is_sent = await self.rpc_request(req, raddr, 'rpc_find_ip', vk_to_find)
                    if is_sent:
                        num_pending_replies += 1
                failed_requests.clear()
            elif num_pending_replies == 0:
                is_done = True
            else:     # increase poll time here
                pinterval = 1000

        return None

    def identity_from_salt(self, salt):
        return '{}:{}:{}'.format(self.vk, self.host_ip, salt).encode()

    def node_from_identity(self, identity):
        vk, ip, salt = identity.split(':')
        node = Node(node_id=digest(vk), vk=vk, ip=ip)

    def generate_router_socket(self, identity, linger=2000, handover=1, mandatory=1):
        router = self.ctx.socket(zmq.ROUTER)

        router.setsockopt(zmq.LINGER, linger)
        router.setsockopt(zmq.ROUTER_HANDOVER, handover)
        router.setsockopt(zmq.ROUTER_MANDATORY, mandatory)

        router.setsockopt(zmq.IDENTITY, self.identity_from_salt(identity))

        return router

    async def network_find_ip(self, event_id, nodes_to_ask, vk_to_find, is_bootstrap=False):
        socket = self.generate_router_socket(event_id)

        node = await self._network_find_ip(socket, nodes_to_ask, vk_to_find, is_bootstrap)

        socket.close()
        return node

    async def find_ip(self, event_id, vk_to_find):
        self.log.info("find_ip called for vk {} with event_id {}".format(vk_to_find, event_id))
        nodes = self.routing_table.find_node(Node(digest(vk_to_find), vk=vk_to_find))

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

        nodes_to_ask = self.routing_table.find_node(Node(digest(vk_to_find), vk=vk_to_find))

        node = await self._network_find_ip(req, nodes_to_ask, vk_to_find, False)
        if node:          # found it, now announce myself
            await self._network_find_ip(req, [node], self.vk, False)
            status = True
        else:
            status = False
        req.close()    # clean up socket  # handle the errors on remote properly
        return node

    # Ping on discovery server?
    async def _ping_ip(self, req, vk, ip, is_first_time):
        raddr = '{}:{}:{}'.format(vk, ip, self.port).encode()
        overlay_address = 'tcp://{}:{}'.format(ip, self.port)
        await req.connect(overlay_address)

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
        self.log.info("find_ip_and_authenticate called for vk {} with event_id {}".format(vk_to_find, event_id))
        ip = self.find_ip(event_id, vk_to_find)
        is_auth = False
        if ip:
            # raghu TODO if is_first_time, announce it as node_on_line - that is on the other side
            # is_auth = await self.handshake.authenticate(event_id, vk_to_find, ip, domain, is_first_time)
            is_auth = await self.ping_ip(event_id, vk_to_find, ip, is_first_time)
        return ip, is_auth


