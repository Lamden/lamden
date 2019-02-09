"""
Package for interacting on the network at a high level.
"""
import random
import pickle
import asyncio
import logging
import os
import zmq, zmq.asyncio

from cilantro.protocol.overlay.kademlia.protocol import KademliaProtocol
from cilantro.protocol.overlay.kademlia.utils import digest
from cilantro.protocol.overlay.kademlia.node import Node
from cilantro.protocol.overlay.kademlia.crawling import NodeSpiderCrawl
from cilantro.constants.ports import DHT_PORT
from cilantro.constants.overlay_network import *
from cilantro.protocol.comm.socket_auth import SocketAuth
from cilantro.logger.base import get_logger
from cilantro.utils.keys import Keys

log = get_logger(__name__)


class Network(object):
    """
    High level view of a node instance.  This is the object that should be
    created to start listening as an active node on the network.
    """

    def __init__(self, ksize=4, alpha=2, node_id=None, loop=None, ctx=None):
        """
        Create a server instance.  This will start listening on the given port.

        Args:
            ksize (int): The k parameter from the paper
            alpha (int): The alpha parameter from the paper
            node_id: The id for this node on the network.
        """
        self.ksize = ksize
        self.alpha = alpha
        self.port = DHT_PORT
        self.cached_vks = {}
        self.host_ip = HOST_IP

        assert Keys.is_setup, 'Keys.setup() has not been called. Please do this in the OverlayInterface.'
        assert node_id, 'Node ID must be set!'

        self.node = Node(
            node_id,
            ip=HOST_IP,
            port=self.port,
            vk=Keys.vk
        )
        self.state_fname = '{}-network-state.dat'.format(os.getenv('HOST_NAME', 'node'))

        self.loop = loop or asyncio.get_event_loop()
        # asyncio.set_event_loop(self.loop)
        self.ctx = ctx or zmq.asyncio.Context()
        self.protocol = KademliaProtocol(self.node, self.ksize, self.loop, self.ctx)

        self.tasks = [
            self.protocol.listen(),
            self.refresh_table(),
            # self.saveStateRegularly()
        ]

    def start(self):
        self.loop.run_until_complete(asyncio.gather(
            *self.tasks
        ))

    def stop(self):
        self.tasks.cancel()

    async def refresh_table(self):
        log.debug("Refreshing routing table")
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
        await self.refresh_table()

    def bootstrappableNeighbors(self):
        """
        Get a :class:`list` of (ip, port, vk) :class:`tuple` pairs suitable for
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

        log.debug("Attempting to bootstrap node with {} initial contacts: {}".format(len(addrs), addrs))

        processed = set()
        processed.add(self.node.vk)
        nearest = []
        futures = []
        for addr in addrs:
            if addr.vk in processed:
                continue
            processed.add(addr.vk)
            futures.append(self.protocol.callFindNode(addr, self.node))
        results = await asyncio.gather(*futures)
        for r in results:
            if r != None:
                nearest.extend(r)
        futures = []
        for addr in nearest:
            if addr.vk in processed:
                continue
            processed.add(addr.vk)
            futures.append(self.protocol.callFindNode(addr, self.node, False))
        results = await asyncio.gather(*futures)

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
        if Keys.vk == vk:
            self.cached_vks[vk] = self.host_ip
            return self.host_ip
        elif vk in self.cached_vks:
            ip = self.cached_vks.get(vk)
            log.debug('"{}" found in cache resolving to {}'.format(vk, ip))
            return ip
        else:
            node_to_find = Node(digest(vk), vk=vk)
            nearest = self.protocol.router.findNode(node_to_find)
            nd = self.get_node_from_nodes_list(vk, nearest)
            num_hops = 1
            if nd:
                log.debug('"{}" found in routing table resolving to {}'.format(vk, nd.ip))
                self.cached_vks[vk] = nd.ip
                return nd.ip
            processed = set()
            while len(nearest) > 0:
                futures = []
                for node in nearest:
                    if node.vk not in processed:
                        futures.append(self._find_node(node, node_to_find))
                        processed.add(node.vk)
                results = await asyncio.gather(*futures)
                for r in results:
                    if r == None: continue
                    nd = self.get_node_from_nodes_list(vk, r)
                    if nd:
                        log.debug('"{}" resolved to {}'.format(vk, nd.ip))
                        self.cached_vks[vk] = nd.ip
                        return nd.ip
                    if type(r) == list:
                        nearest += r
                    else:
                        nearest.append(r)

            return None

    async def _find_node(self, node, node_to_find):
        try:
            fut = asyncio.ensure_future(self.protocol.callFindNode(node, node_to_find))
            await asyncio.wait_for(fut, 12)
            return fut.result()
        except asyncio.TimeoutError:
            log.warning("find_node timed out asking node {} for node_to_find {}".format(node, node_to_find))

    def get_node_from_nodes_list(self, vk, nodes):
        for node in nodes:
            if vk == node.vk:
                return node

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
        with open(fname, 'wb+') as f:
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
        s = Server(data['ksize'], data['alpha'], data['id'])
        if len(data['neighbors']) > 0:
            s.bootstrap(data['neighbors'])
        return s

    async def saveStateRegularly(self, fname=None, frequency=600):
        """
        Save the state of node with a given regularity to the given
        filename.

        Args:
            fname: File name to save retularly to
            frequency: Frequency in seconds that the state should be saved.
                        By default, 10 minutes.
        """
        fname = fname or self.state_fname
        self.saveState(fname)
        await asyncio.sleep(frequency)
        self.saveStateRegularly(fname, frequency)
