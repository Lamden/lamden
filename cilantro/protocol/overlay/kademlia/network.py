"""
Package for interacting on the network at a high level.
"""
import random
import pickle
import asyncio
import logging

from cilantro.constants.overlay_network import *
from cilantro.constants.ports import DHT_PORT
from cilantro.protocol.overlay.kademlia.protocol import KademliaProtocol
from cilantro.protocol.overlay.kademlia.utils import digest
from cilantro.protocol.overlay.kademlia.node import Node
from cilantro.protocol.overlay.kademlia.crawling import ValueSpiderCrawl
from cilantro.protocol.overlay.kademlia.crawling import NodeSpiderCrawl
from cilantro.protocol.overlay.auth import Auth

from cilantro.logger.base import get_logger
log = get_logger(__name__)

class Network(object):
    """
    High level view of a node instance.  This is the object that should be
    created to start listening as an active node on the network.
    """
    host_ip = HOST_IP
    port = DHT_PORT
    protocol_class = KademliaProtocol

    def __init__(self, ksize=20, alpha=3, loop=None):
        """
        Create a server instance.  This will start listening on the given port.

        Args:
            ksize (int): The k parameter from the paper
            alpha (int): The alpha parameter from the paper
            vk: The vk for this node on the network.
        """
        self.ksize = ksize
        self.alpha = alpha
        self.loop = loop or asyncio.get_event_loop()
        self.node = Node(node_id=digest(Auth.vk), ip=self.host_ip, port=self.port, vk=Auth.vk)
        self.transport = None
        self.protocol = None
        self.refresh_loop = None
        self.save_state_loop = None
        self.cached_vks = {}

    def stop(self):
        if self.transport is not None:
            self.transport.close()

        if self.refresh_loop:
            self.refresh_loop.cancel()

        if self.save_state_loop:
            self.save_state_loop.cancel()

    def _create_protocol(self):
        return self.protocol_class(self.node, self.ksize)

    async def listen(self, interface='0.0.0.0'):
        """
        Start listening on the given port.

        Provide interface="::" to accept ipv6 address
        """
        loop = self.loop
        listen = loop.create_datagram_endpoint(self._create_protocol,
                                               local_addr=(interface, self.port))
        log.spam("Node %i listening on %s:%i",
                 self.node.long_id, interface, self.port)
        self.transport, self.protocol = await asyncio.ensure_future(listen)
        await self._refresh_table()

    async def _refresh_table(self):
        """
        Refresh buckets that haven't had any lookups in the last hour
        (per section 2.3 of the paper).
        """
        ds = []
        for node_id in self.protocol.getRefreshIDs():
            node = Node(node_id)
            nearest = self.protocol.router.findNeighbors(node, self.alpha)
            spider = NodeSpiderCrawl(self.protocol, node, nearest,
                                     self.ksize, self.alpha)
            ds.append(spider.find())

        # do our crawling
        await asyncio.gather(*ds)

        await asyncio.sleep(3600)
        await self._refresh_table()

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
        return [tuple(n)[1:] for n in neighbors]

    async def bootstrap(self, addrs):
        """
        Bootstrap the server by connecting to other known nodes in the network.

        Args:
            addrs: A `list` of (ip, port) `tuple` pairs.  Note that only IP
                   addresses are acceptable - hostnames will cause an error.
        """
        log.spam("Attempting to bootstrap node with %i initial contacts",
                  len(addrs))
        cos = list(map(self.bootstrap_node, addrs))
        gathered = await asyncio.gather(*cos)
        nodes = [node for node in gathered if node is not None]
        spider = NodeSpiderCrawl(self.protocol, self.node, nodes,
                                 self.ksize, self.alpha)
        return await spider.find()

    async def bootstrap_node(self, addr):
        result = await self.protocol.ping(addr, self.node.id, self.node.vk)
        if result[0]:
            nodeid, vk = result[1]
            return Node(nodeid, addr[0], addr[1], vk)

    async def lookup_ip(self, vk):
        log.spam('Attempting to look up node with vk="{}"'.format(vk))
        if Auth.vk == vk:
            self.cached_vks[vk] = self.host_ip
            return self.host_ip
        elif self.cached_vks.get(vk):
            node = self.cached_vks.get(vk)
            log.debug('"{}" found in cache resolving to {}'.format(vk, node))
            return node.ip
        else:
            nearest = self.protocol.router.findNeighbors(self.node)
            spider = NodeSpiderCrawl(self.protocol, Node(digest(vk)),
                                    nearest, self.ksize, self.alpha)
            nodes = await spider.find()
            for node in nodes:
                if node.vk == vk:
                    log.debug('"{}" resolved to {}'.format(vk, node))
                    self.cached_vks[vk] = node.ip
                    return node.ip
            log.warning('"{}" cannot be resolved (asked {})'.format(vk, node))
            return None

    def saveState(self, fname):
        """
        Save the state of this node (the alpha/ksize/id/immediate neighbors)
        to a cache file with the given fname.
        """
        log.spam("Saving state to %s", fname)
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
        log.spam("Loading state from %s", fname)
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
        loop = asyncio.get_event_loop()
        self.save_state_loop = loop.call_later(frequency,
                                               self.saveStateRegularly,
                                               fname,
                                               frequency)
