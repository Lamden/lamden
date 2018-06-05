"""
Package for interacting on the network at a high level.
"""
import random
import pickle
import asyncio
import logging
import os, zmq
import socket, select

from nacl.signing import VerifyKey
from cilantro.logger import get_logger
from cilantro.protocol.overlay.protocol import KademliaProtocol
from cilantro.protocol.overlay.utils import digest
from cilantro.protocol.overlay.storage import ForgetfulStorage
from cilantro.protocol.overlay.node import Node
from cilantro.protocol.overlay.crawling import ValueSpiderCrawl, NodeSpiderCrawl
from cilantro.protocol.overlay.ironhouse import Ironhouse

if hasattr(select, 'epoll'):
    poll = select.epoll
    POLLIN = select.EPOLLIN
else:
    poll = select.poll
    POLLIN = select.POLLIN

log = get_logger(__name__)

class Network(object):
    """
    High level view of a node instance.  This is the object that should be
    created to start listening as an active node on the network.
    """

    protocol_class = KademliaProtocol

    def __init__(self, ksize=20, alpha=3, node_id=None, storage=None, discovery_mode='neighborhood', loop=None, max_peers=64, *args, **kwargs):
        """
        Create a server instance.  This will start listening on the given port.

        Args:
            ksize (int): The k parameter from the paper
            alpha (int): The alpha parameter from the paper
            node_id: The id for this node on the network.
            storage: An instance that implements
                     :interface:`~cilantro.protocol.overlay.storage.IStorage`
        """
        self.loop = loop if loop else asyncio.get_event_loop()
        asyncio.set_event_loop(self.loop)
        self.ksize = ksize
        self.alpha = alpha
        self.port = os.getenv('NETWORK_PORT', 5678)
        self.storage = storage or ForgetfulStorage()
        self.ironhouse = Ironhouse(*args, **kwargs)
        self.node = Node(node_id=digest(self.ironhouse.vk), public_key=self.ironhouse.public_key)
        self.transport = None
        self.protocol = None
        self.refresh_loop = None
        self.save_state_loop = None
        self.max_peers = max_peers
        self.setup_stethoscope()
        self.ironhouse.setup_secure_server()

    def authenticate(self, node):
        return self.ironhouse.authenticate(node.public_key, node.ip)

    def setup_stethoscope(self):
        socket.setdefaulttimeout(0.1)
        self.heartbeat_port = os.getenv('HEARTBEAT_PORT', 31233)
        self.stethoscope_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.stethoscope_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.stethoscope_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.stethoscope_sock.setblocking(0)
        self.stethoscope_sock.bind(('0.0.0.0', self.heartbeat_port))
        self.stethoscope_sock.listen(self.max_peers)
        asyncio.ensure_future(self.stethoscope())

    async def stethoscope(self):
        self.connections = {}
        self.poll = poll()
        self.poll.register(self.stethoscope_sock.fileno(), POLLIN)
        try:
            while True:
                events = self.poll.poll(1)
                for fileno, event in events:
                    if fileno == self.stethoscope_sock.fileno():
                        conn, addr = self.stethoscope_sock.accept()
                        log.info("[SERVER SIDE] Client (%s, %s) connected to server" % addr)
                    elif event & (POLLIN):
                        conn, addr, node = self.connections[fileno]
                        try:
                            conn.connect(addr)
                        except Exception as e:
                            if e.args[0] == 104:
                                log.info("Client (%s, %s) disconnected" % addr)
                                self.poll.unregister(fileno)
                                conn.close()
                                del self.connections[fileno]
                                self.protocol.router.removeContact(node)
                await asyncio.sleep(0.1)
        finally:
            self.poll.unregister(self.stethoscope_sock.fileno())
            self.poll.close()
            self.stethoscope_sock.close()

    def connect_to_neighbor(self, node):
        if self.node.id == node.id: return
        addr = (node.ip, self.heartbeat_port)
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connections[conn.fileno()] = (conn, addr, node)
        try:
            conn.connect(addr)
            self.poll.register(conn.fileno(), POLLIN)
            log.info("[CLIENT SIDE] Client (%s, %s) connected" % addr)
        except:
            del self.connections[conn.fileno()]
            pass

    async def lookup_ip(self, node_key):
        node_id = digest(node_key)
        public_key = VerifyKey(bytes.fromhex(node_key)).to_curve25519_public_key()._public_key.hex()
        node = Node(node_id=node_id, public_key=public_key)

        Node(node_id=digest(self.ironhouse.vk), public_key=self.ironhouse.public_key)
        nearest = self.protocol.router.findNeighbors(self.node)
        spider = NodeSpiderCrawl(self.protocol, node, nearest, self.ksize, self.alpha)

        log.debug("Starting lookup for node_key {}".format(node_key))
        res_node = await spider.find(node_id=node_id)

        if type(res_node) == list: res_node = None
        log.debug('{} resolves to {}'.format(node_key, res_node))

        return res_node

    def stop(self):
        if self.transport is not None:
            self.transport.close()

        if self.refresh_loop:
            self.refresh_loop.cancel()

        if self.save_state_loop:
            self.save_state_loop.cancel()

        try:
            self.poll.unregister(self.stethoscope_sock.fileno())
            self.poll.close()
            self.stethoscope_sock.close()
            self.udp_sock_server.close()
            self.ironhouse.sec_sock.close()
        except Exception as e:
            log.debug(e)

    def _create_protocol(self):
        return self.protocol_class(self.node, self.storage, self.ksize, self)

    def listen(self, port, interface='0.0.0.0'):
        """
        Start listening on the given port.

        Provide interface="::" to accept ipv6 address
        """
        listen = self.loop.create_datagram_endpoint(self._create_protocol,
                                               local_addr=(interface, port))
        log.info("Node %i listening on %s:%i",
                 self.node.long_id, interface, port)
        self.transport, self.protocol = self.loop.run_until_complete(listen)
        # finally, schedule refreshing table
        self.refresh_table()

    def refresh_table(self):
        asyncio.ensure_future(self._refresh_table())
        self.refresh_loop = self.loop.call_later(3600, self.refresh_table)

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

        # now republish keys older than one hour
        for dkey, value in self.storage.iteritemsOlderThan(3600):
            await self.set_digest(dkey, value)

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
        return [tuple(n)[-2:] for n in neighbors]

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
        spider = NodeSpiderCrawl(self.protocol, self.node, nodes,
                                 self.ksize, self.alpha)
        res = await spider.find()
        return res

    async def bootstrap_node(self, addr):
        result = await self.protocol.ping(addr, self.node.public_key, self.node.id)
        if result[0]:
            node_id, public_key = result[1]
            return Node(node_id, addr[0], addr[1], public_key=public_key)

    async def get(self, key):
        """
        Get a key if the network has it.

        Returns:
            :class:`None` if not found, the value otherwise.
        """
        log.info("Looking up key %s", key)
        dkey = digest(key)
        # if this node has it, return it
        if self.storage.get(dkey) is not None:
            return self.storage.get(dkey)
        node = Node(dkey)
        nearest = self.protocol.router.findNeighbors(node)
        if len(nearest) == 0:
            log.warning("There are no known neighbors to get key %s", key)
            return None
        spider = ValueSpiderCrawl(self.protocol, node, nearest,
                                  self.ksize, self.alpha)
        return await spider.find()

    async def set(self, key, value):
        """
        Set the given string key to the given value in the network.
        """
        if not check_dht_value_type(value):
            raise TypeError(
                "Value must be of type int, float, bool, str, or bytes"
            )
        log.info("setting '%s' = '%s' on network", key, value)
        dkey = digest(key)
        return await self.set_digest(dkey, value)

    async def set_digest(self, dkey, value):
        """
        Set the given sha1 digest key (bytes) to the given value in the
        network.
        """
        node = Node(dkey)

        nearest = self.protocol.router.findNeighbors(node)
        if len(nearest) == 0:
            log.warning("There are no known neighbors to set key %s",
                        dkey.hex())
            return False

        spider = NodeSpiderCrawl(self.protocol, node, nearest,
                                 self.ksize, self.alpha)
        nodes = await spider.find()
        log.info("setting '%s' on %s", dkey.hex(), list(map(str, nodes)))

        # if this node is close too, then store here as well
        biggest = max([n.distanceTo(node) for n in nodes])
        if self.node.distanceTo(node) < biggest:
            self.storage[dkey] = value
        ds = [self.protocol.callStore(n, dkey, value) for n in nodes]
        # return true only if at least one store call succeeded
        return any(await asyncio.gather(*ds))

    def saveState(self, fname):
        """
        Save the state of this node (the alpha/ksize/id/immediate neighbors)
        to a cache file with the given fname.
        """
        log.info("Saving state to %s", fname)
        data = {
            'ksize': self.ksize,
            'alpha': self.alpha,
            'id': self.node.id,
            'neighbors': self.bootstrappableNeighbors()
        }
        if len(data['neighbors']) == 0:
            log.warning("No known neighbors, so not writing to cache.")
            return
        with open(fname, 'wb') as f:
            pickle.dump(data, f)

    @classmethod
    def loadState(self, fname):
        """
        Load the state of this node (the alpha/ksize/id/immediate neighbors)
        from a cache file with the given fname.
        """
        log.info("Loading state from %s", fname)
        with open(fname, 'rb') as f:
            data = pickle.load(f)
        s = Network(data['ksize'], data['alpha'], data['id'])
        if len(data['neighbors']) > 0:
            s.bootstrap(data['neighbors'])
        return s

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


def check_dht_value_type(value):
    """
    Checks to see if the type of the value is a valid type for
    placing in the dht.
    """
    typeset = set(
        [
            int,
            float,
            bool,
            str,
            bytes,
        ]
    )
    return type(value) in typeset

if __name__ == '__main__':
    s = Network(node_id='vk_'.format(os.getenv('HOST_IP', '127.0.0.1')), discovery_mode='test')
    loop = asyncio.get_event_loop()
    loop.run_forever()
