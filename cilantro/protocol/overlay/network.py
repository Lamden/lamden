"""
Package for interacting on the network at a high level.
"""

import pickle
import asyncio
import os

import socket, select, ujson

from cilantro.logger import get_logger
from cilantro.protocol.structures import Bidict
from cilantro.protocol.overlay.protocol import KademliaProtocol
from cilantro.protocol.overlay.utils import digest
from cilantro.protocol.overlay.node import Node
from cilantro.protocol.overlay.crawling import NodeSpiderCrawl
from cilantro.protocol.overlay.ironhouse import Ironhouse
from cilantro.messages.reactor.reactor_command import ReactorCommand
from cilantro.protocol.states.state import StateInput

try: poll = select.epoll
except: poll = select.poll
try: POLLIN = select.EPOLLIN
except: POLLIN = select.POLLIN

log = get_logger(__name__)

HEARTBEAT_PORT_OFFSET = 1
AUTH_PORT_OFFSET = 2

class Network(object):
    """
    High level view of a node instance.  This is the object that should be
    created to start listening as an active node on the network.
    """

    protocol_class = KademliaProtocol

    def __init__(self, ksize=20, alpha=3, node_id=None, discovery_mode='neighborhood', loop=None, max_peers=64, network_port=None, public_ip=None, event_sock=None, *args, **kwargs):
        """
        Create a server instance.  This will start listening on the given port.
        Args:
            ksize (int): The k parameter from the paper
            alpha (int): The ALPHA parameter from the paper
            node_id: The id for this node on the network.
        """
        self.loop = loop if loop else asyncio.get_event_loop()
        asyncio.set_event_loop(self.loop)
        self.vkcache = {}
        self.ksize = ksize
        self.alpha = alpha
        self.transport = None
        self.protocol = None
        self.refresh_loop = None
        self.save_state_loop = None
        self.event_sock = event_sock
        self.max_peers = max_peers
        self.network_port = network_port
        self.heartbeat_port = self.network_port+HEARTBEAT_PORT_OFFSET
        self.ironhouse = Ironhouse(auth_port=self.network_port+AUTH_PORT_OFFSET, *args, **kwargs)
        self.node = Node(
            node_id=digest(self.ironhouse.vk),
            public_key=self.ironhouse.public_key,
            ip=public_ip or os.getenv('HOST_IP', '127.0.0.1'),
            port=self.network_port
        )
        self.setup_stethoscope()
        self.ironhouse.setup_secure_server()
        self.listen()
        self.saveStateRegularly('state.tmp')

    async def authenticate(self, node):
        authorization = await self.ironhouse.authenticate(node.public_key, node.ip, node.port+AUTH_PORT_OFFSET)
        log.debug('{}:{}\'s authorization is {}'.format(node.ip, node.port, authorization))
        if authorization == 'authorized':
            self.protocol.router.addContact(node)
            self.connect_to_neighbor(node)
            self.vkcache[node.id] = node
            self.ironhouse.authorized_nodes[node.id] = node.ip
        elif authorization == 'unauthorized':
            try: self.protocol.router.removeContact(node)
            except: pass
            self.ironhouse.authorized_nodes[node.id] = False
            if self.event_sock: self.event_sock.send_json({'event':'unauthorized', 'ip': node.ip})
        log.debug('{}\'s New Authorized list: {}'.format(os.getenv('HOST_IP', '127.0.0.1'), [self.vkcache.get(k).ip for k in self.ironhouse.authorized_nodes if self.vkcache.get(k)]))
        return authorization == 'authorized'

    def setup_stethoscope(self):
        socket.setdefaulttimeout(0.1)
        self.stethoscope_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.stethoscope_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.stethoscope_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.stethoscope_sock.setblocking(0)
        self.stethoscope_sock.bind(('0.0.0.0', self.heartbeat_port))
        self.stethoscope_sock.listen(self.max_peers)
        self.stethoscope_future = asyncio.ensure_future(self.stethoscope())

    async def stethoscope(self):
        self.connections = {}
        self.poll = poll()
        log.debug('Listening to heartbeats on {}...'.format(self.heartbeat_port))
        try:
            while True:
                events = self.poll.poll(1)
                for fileno, event in events:
                    if event & (POLLIN):
                        conn, node = self.connections[fileno]
                        addr = (node.ip, node.port+HEARTBEAT_PORT_OFFSET)
                        try:
                            log.debug('reconnecting {} - {}'.format(self.network_port, addr))
                            conn.connect(addr)
                        except Exception as e:
                            log.debug(e.args)
                            if e.args[1] == 'Connection reset by peer':
                                log.info("Client ({}, {}) disconnected from {}".format(*addr, self.node))
                                del self.connections[fileno]
                                self.protocol.router.removeContact(node)
                                self.poll.unregister(fileno)
                                conn.close()
                                self.connection_drop(node)
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            log.info('Network shutting down gracefully.')

    def connection_drop(self, node):
        if self.event_sock: self.event_sock.send_json({'event':'disconect', 'ip':node.ip, 'vk': self.ironhouse.pk2vk.get(node.public_key) })
        callback = ReactorCommand.create_callback(
            callback=StateInput.CONN_DROPPED,
            ip=node.ip
        )
        log.debug("Sending callback failure to mainthread {}".format(callback))

    def connect_to_neighbor(self, node):
        if self.node.id == node.id: return

        addr = (node.ip, node.port+HEARTBEAT_PORT_OFFSET)
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connections[conn.fileno()] = (conn, node)
        try:
            conn.connect(addr)
            self.poll.register(conn.fileno(), POLLIN)
            log.info("[CLIENT SIDE] Client ({}, {}) connected".format(*addr))
            if self.event_sock: self.event_sock.send_json({'event':'connected', 'ip': addr[0], 'vk': self.ironhouse.pk2vk.get(node.public_key)})
            return conn
        except Exception as e:
            del self.connections[conn.fileno()]
            conn.close()

    def lookup_ip_in_cache(self, id):
        node = self.vkcache.get(id)
        if node:
            log.debug('Found ip {} in cache'.format(node.ip))
        return node

    async def lookup_ip(self, node_key):
        node_id = digest(node_key)
        cache_node = self.lookup_ip_in_cache(node_id)
        if cache_node: return cache_node, True
        if node_id == self.node.id: return self.node

        nearest = self.protocol.router.findNeighbors(self.node)
        spider = NodeSpiderCrawl(self.protocol, self.node, nearest, self.ksize, self.alpha)

        log.debug("Starting lookup for node_key {}".format(node_key))
        res_node = await spider.find(node_id=node_id)

        if type(res_node) == list: res_node = None
        log.debug('VK {} resolves to {}'.format(node_key, res_node))
        if res_node != None:
            self.vkcache[node_id] = res_node
            pk = self.ironhouse.vk2pk(node_key)
        return res_node, False

    def stop(self):
        if self.transport is not None:
            self.transport.close()

        if not self.refresh_future.done():
            self.refresh_future.set_result('done')

        if self.refresh_loop:
            self.refresh_loop.cancel()

        if self.save_state_loop:
            self.save_state_loop.cancel()

        for fileno in self.connections:
            conn, node = self.connections[fileno]
            try: self.poll.unregister(fileno)
            except: log.debug('Already unregistered')
            conn.close()
            log.debug('Closed a previously opened connection')

        self.ironhouse.cleanup()

        try: self.poll.unregister(self.stethoscope_sock.fileno())
        except: log.debug('Stehoscope is already unregistered')
        self.stethoscope_sock.close()
        try: self.poll.close()
        except: pass#log.debug('Not epoll object, no need to close.')
        self.stethoscope_future.cancel()

    def _create_protocol(self):
        return self.protocol_class(self.node, self.ksize, self)

    def listen(self, port=None, interface='0.0.0.0'):
        """
        Start listening on the given port.
        Provide interface="::" to accept ipv6 address
        """
        port = self.network_port
        listen = self.loop.create_datagram_endpoint(self._create_protocol,
                                               local_addr=(interface, port))
        log.info("Listening to kade network on %s:%i",
                 interface, port)
        self.transport, self.protocol = self.loop.run_until_complete(listen)
        # finally, schedule refreshing table
        self.refresh_table()

    def refresh_table(self):
        self.refresh_loop = self.loop.call_later(3600, self.refresh_table)
        self.refresh_future = asyncio.ensure_future(self._refresh_table())
        return self.refresh_future

    async def _refresh_table(self):
        """
        Refresh buckets that haven't had any lookups in the last hour
        (per section 2.3 of the paper).
        """
        log.debug("Refreshing routing table")
        ds = []
        for node_id in self.protocol.getRefreshIDs():
            node = Node(node_id=node_id)
            nearest = self.protocol.router.findNeighbors(node, self.alpha)
            spider = NodeSpiderCrawl(self.protocol, node, nearest,
                                     self.ksize, self.alpha)
            ds.append(spider.find())

        # do our crawling
        await asyncio.gather(*ds)
        if self.event_sock: self.event_sock.send_json({'event':'table_refreshed'})

    def bootstrappableNeighbors(self):
        """
        Get a :class:`list` of (ip, port) :class:`tuple` pairs suitable for
        use as an argument to the bootstrap method.
        The server should have been bootstrapped
        already - this is just a utility for getting some neighbors and then
        storing them if this server is going down for a while.  When it comes
        back up, the list of nodes can be used to bootstrap.
        """
        neighbors = self.protocol.router.findNeighbors(self.node)
        return [tuple(n)[-3:] for n in neighbors]

    async def bootstrap(self, addrs):
        """
        Bootstrap the server by connecting to other known nodes in the network.
        Args:
            addrs: A `list` of (ip, port) `tuple` pairs.  Note that only IP
                   addresses are acceptable - hostnames will cause an error.
        """
        log.debug("Attempting to bootstrap node with %i initial contacts",
                  len(addrs))
        cos = list(map(self.bootstrap_node, addrs))
        gathered = await asyncio.gather(*cos)
        nodes = [node for node in gathered if node is not None]

        if len(nodes) == 0:
            log.warning('Unable to find/authenticate with any nodes in the network')
            return []

        spider = NodeSpiderCrawl(self.protocol, self.node, nodes,
                                 self.ksize, self.alpha)
        res = await spider.find()
        return res

    async def bootstrap_node(self, addr):
        result = await self.protocol.ping(addr, self.node.public_key, self.node.id)
        if result[0]:
            node_id, public_key = result[1]
            node = Node(node_id, ip=addr[0], port=addr[1], public_key=public_key)
            authorized = await self.authenticate(node)
            if authorized == True:
                return node
        return None

    def saveState(self, fname):
        """
        Save the state of this node (the ALPHA/KSIZE/id/immediate neighbors)
        to a cache file with the given fname.
        """
        log.info("Saving state to %s", fname)
        data = {
            'KSIZE': self.ksize,
            'ALPHA': self.alpha,
            'id': self.node.id,
            'neighbors': self.bootstrappableNeighbors()
        }
        if len(data['neighbors']) == 0:
            log.info("No known neighbors, so not writing to cache.")
            return False
        with open(fname, 'wb+') as f:
            pickle.dump(data, f)
        return True

    @classmethod
    def loadState(self, fname):
        """
        Load the state of this node (the ALPHA/KSIZE/id/immediate neighbors)
        from a cache file with the given fname.
        """
        log.info("Loading state from %s", fname)
        with open(fname, 'rb') as f:
            data = pickle.load(f)
        return data

    def saveStateRegularly(self, fname, frequency=600):
        """
        Save the state of node with a given regularity to the given
        filename.
        Args:
            fname: File name to save retularly to
            frequency: Frequency in seconds that the state should be saved.
                        By default, 10 minutes.
        """
        self.saveState(fname)
        self.save_state_loop = self.loop.call_later(frequency,
                                               self.saveStateRegularly,
                                               fname,
                                               frequency)
