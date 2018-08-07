import random
import asyncio

from rpcudp.protocol import RPCProtocol
from cilantro.logger import get_logger
from cilantro.protocol.overlay.node import Node
from cilantro.protocol.overlay.routing import RoutingTable
from cilantro.protocol.overlay.utils import digest
from cilantro.constants.overlay_network import rpc_timeout

log = get_logger(__name__)


class KademliaProtocol(RPCProtocol):
    def __init__(self, sourceNode, ksize, network):
        RPCProtocol.__init__(self, waitTimeout=rpc_timeout)
        self.router = RoutingTable(self, ksize, sourceNode)
        self.sourceNode = sourceNode
        self.network = network

    def getRefreshIDs(self):
        """
        Get ids to search for to keep old buckets up to date.
        """
        ids = []
        # TODO re-run discovery here
        for bucket in self.router.getLonelyBuckets():
            rid = random.randint(*bucket.range).to_bytes(20, byteorder='big')
            ids.append(rid)
        return ids

    def rpc_ping(self, sender, public_key, nodeid):
        source = Node(nodeid, sender[0], sender[1], public_key=public_key)
        self.welcomeIfNewNode(source)
        return self.sourceNode.id, self.sourceNode.public_key

    def rpc_find_node(self, sender, public_key, nodeid, key):
        log.info("finding neighbors of %i in local table",
                 int(nodeid.hex(), 16))
        source = Node(nodeid, sender[0], sender[1], public_key=public_key)
        self.welcomeIfNewNode(source)
        node = Node(key)
        neighbors = self.router.findNeighbors(node, exclude=source)
        return list(map(tuple, neighbors))

    async def callFindNode(self, nodeToAsk, nodeToFind):
        address = (nodeToAsk.ip, nodeToAsk.port)
        result = await self.find_node(address, self.sourceNode.public_key, self.sourceNode.id,
                                      nodeToFind.id)
        # if not await self.network.authenticate(nodeToAsk):
        #     nodeToAsk = None
        return self.handleCallResponse(result, nodeToAsk)

    async def callPing(self, nodeToAsk):
        address = (nodeToAsk.ip, nodeToAsk.port)
        result = await self.ping(address, self.sourceNode.public_key, self.sourceNode.id)
        # if not await self.network.authenticate(nodeToAsk):
        #     nodeToAsk = None
        return self.handleCallResponse(result, nodeToAsk)

    def welcomeIfNewNode(self, node):
        """
        Given a new node, send it all the keys/values it should be storing,
        then add it to the routing table.

        @param node: A new node that just joined (or that we just found out
        about).

        Process:
        For each key in storage, get k closest nodes.  If newnode is closer
        than the furtherst in that list, and the node for this network
        is closer than the closest in that list, then store the key/value
        on the new node (per section 2.5 of the paper)
        """
        if not node:
            log.warning('This node is not welcomed.')
            return

        if not self.router.isNewNode(node):
            log.debug("Skipping node {} that already exists in routing table".format(node))
            return

        log.info("never seen %s before, adding to router", node)

        self.router.addContact(node)
        self.network.connect_to_neighbor(node)

    def handleCallResponse(self, result, node):
        """
        If we get a response, add the node to the routing table.  If
        we get no response, make sure it's removed from the routing table.
        """
        if not result[0]:
            # if node:
            #     log.warning("no response from %s, removing from router", node)
            #     self.router.removeContact(node)
            return result

        log.info("got successful response from %s", node)
        self.welcomeIfNewNode(node)
        return result
