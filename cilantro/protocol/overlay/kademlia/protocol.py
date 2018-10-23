import random
import asyncio
import logging

from cilantro.protocol.overlay.kademlia.rpczmq import RPCProtocol

from cilantro.protocol.overlay.kademlia.node import Node
from cilantro.protocol.overlay.kademlia.routing import RoutingTable
from cilantro.protocol.overlay.kademlia.utils import digest

log = logging.getLogger(__name__)


class KademliaProtocol(RPCProtocol):
    def __init__(self, sourceNode, ksize, loop=None, ctx=None):
        RPCProtocol.__init__(self, loop, ctx)
        self.router = RoutingTable(self, ksize, sourceNode)
        self.sourceNode = sourceNode

    def getRefreshIDs(self):
        """
        Get ids to search for to keep old buckets up to date.
        """
        ids = []
        for bucket in self.router.getLonelyBuckets():
            rid = random.randint(*bucket.range).to_bytes(20, byteorder='big')
            ids.append(rid)
        return ids

    def rpc_stun(self, sender):
        return sender

    def rpc_ping(self, sender, nodeid):
        source = Node(nodeid, sender[0], sender[1], sender[2])
        self.welcomeIfNewNode(source)
        return self.sourceNode.id

    def rpc_find_node(self, sender, nodeid, key):
        log.info("finding neighbors of %i in local table",
                 int(nodeid.hex(), 16))
        source = Node(nodeid, sender[0], sender[1], sender[2])
        self.welcomeIfNewNode(source)
        node = Node(key)
        neighbors = self.router.findNeighbors(node, exclude=source)
        return list(map(tuple, neighbors))

    async def callFindNode(self, nodeToAsk, nodeToFind):
        address = (nodeToAsk.ip, nodeToAsk.port, self.sourceNode.vk)
        result = await self.find_node(address, self.sourceNode.id,
                                      nodeToFind.id)
        return self.handleCallResponse(result, nodeToAsk)

    async def callPing(self, nodeToAsk):
        address = (nodeToAsk.ip, nodeToAsk.port, self.sourceNode.vk)
        result = await self.ping(address, self.sourceNode.id)
        return self.handleCallResponse(result, nodeToAsk)

    def welcomeIfNewNode(self, node):
        """
        Given a new node, send it all the keys/values it should be storing,
        then add it to the routing table.

        @param node: A new node that just joined (or that we just found out
        about).

        Process (deprecated):
        For each key in storage, get k closest nodes.  If newnode is closer
        than the furtherst in that list, and the node for this server
        is closer than the closest in that list, then store the key/value
        on the new node (per section 2.5 of the paper)
        """
        if not self.router.isNewNode(node):
            return

        log.info("never seen %s before, adding to router", node)
        self.router.addContact(node)

    def handleCallResponse(self, result, node):
        """
        If we get a response, add the node to the routing table.  If
        we get no response, make sure it's removed from the routing table.
        """
        if not result[0]:
            log.warning("no response from %s, removing from router", node)
            self.router.removeContact(node)
            return result

        log.info("got successful response from %s", node)
        self.welcomeIfNewNode(node)
        return result
