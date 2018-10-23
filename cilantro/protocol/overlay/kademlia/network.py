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
from cilantro.protocol.overlay.kademlia.storage import ForgetfulStorage
from cilantro.protocol.overlay.kademlia.node import Node
from cilantro.protocol.overlay.kademlia.crawling import ValueSpiderCrawl
from cilantro.protocol.overlay.kademlia.crawling import NodeSpiderCrawl
from cilantro.constants.ports import DHT_PORT
from cilantro.constants.overlay_network import *

log = logging.getLogger(__name__)


class Network(object):
    """
    High level view of a node instance.  This is the object that should be
    created to start listening as an active node on the network.
    """

    def __init__(self, ksize=20, alpha=3, node_id=None, storage=None, loop=None, ctx=None):
        """
        Create a server instance.  This will start listening on the given port.

        Args:
            ksize (int): The k parameter from the paper
            alpha (int): The alpha parameter from the paper
            node_id: The id for this node on the network.
            storage: An instance that implements
                     :interface:`~kademlia.storage.IStorage`
        """
        self.ksize = ksize
        self.alpha = alpha
        self.storage = storage or ForgetfulStorage()
        self.port = DHT_PORT
        self.node = Node(
            node_id or digest(random.getrandbits(255)),
            ip=HOST_IP,
            port=self.port
        )
        self.state_fname = '{}/network-state.dat'.format(os.getenv('HOST_NAME', 'node'))

        self.loop = loop or asyncio.get_event_loop()
        asyncio.set_event_loop(self.loop)
        self.ctx = ctx or zmq.asyncio.Context()
        self.protocol = KademliaProtocol(self.node, self.storage, self.ksize, self.loop, self.ctx)

        self.tasks = [
            self.protocol.listen(),
            self.refresh_table(),
            self.saveStateRegularly()
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

        # now republish keys older than one hour
        for dkey, value in self.storage.iteritemsOlderThan(3600):
            await self.set_digest(dkey, value)

        await asyncio.sleep(3600)
        await self.refresh_table()


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
        return await spider.find()

    async def bootstrap_node(self, addr):
        result = await self.protocol.ping(addr, self.node.id)
        return Node(result[1], addr[0], addr[1]) if result[0] else None

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
        Set the given SHA1 digest key (bytes) to the given value in the
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
