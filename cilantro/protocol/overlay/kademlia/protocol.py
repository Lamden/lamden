import random
import asyncio
import logging

from cilantro.protocol.overlay.kademlia.rpcudp import RPCProtocol
from cilantro.constants.overlay_network import RPC_TIMEOUT
from cilantro.protocol.overlay.kademlia.node import Node
from cilantro.protocol.overlay.kademlia.routing import RoutingTable
from cilantro.protocol.overlay.kademlia.utils import digest

from cilantro.logger.base import get_logger
log = get_logger(__name__)


class KademliaProtocol(RPCProtocol):
    def __init__(self, sourceNode, ksize):
        RPCProtocol.__init__(self, waitTimeout=RPC_TIMEOUT)
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

    def rpc_ping(self, sender, nodeid, vk):
        source = Node(nodeid, sender[0], sender[1], vk)
        self.welcomeIfNewNode(source)
        return self.sourceNode.id, self.sourceNode.vk

    def rpc_find_node(self, sender, nodeid, vk, key):
        log.spam("finding neighbors of %i in local table",
                 int(nodeid.hex(), 16))
        source = Node(nodeid, sender[0], sender[1], vk)
        self.welcomeIfNewNode(source)
        node = Node(key)
        neighbors = self.router.findNeighbors(node, exclude=source)
        return list(map(tuple, neighbors))

    def rpc_find_ip(self, sender, nodeid, vk, key):
        log.spam("finding neighbors of %i in local table",
                 int(nodeid.hex(), 16))
        source = Node(nodeid, sender[0], sender[1], vk)
        self.welcomeIfNewNode(source)
        node = Node(key)
        neighbors = self.router.findNeighbors(node)
        return list(map(tuple, neighbors))

    async def callFindNode(self, nodeToAsk, nodeToFind):
        address = (nodeToAsk.ip, nodeToAsk.port)
        result = await self.find_node(address, self.sourceNode.id,
                                      self.sourceNode.vk,
                                      nodeToFind.id)
        return self.handleCallResponse(result, nodeToAsk)

    async def callFindIp(self, nodeToAsk, nodeToFind):
        address = (nodeToAsk.ip, nodeToAsk.port)
        result = await self.find_ip(address, self.sourceNode.id,
                                      self.sourceNode.vk,
                                      nodeToFind.id)
        return self.handleCallResponse(result, nodeToAsk)

    async def callPing(self, nodeToAsk):
        address = (nodeToAsk.ip, nodeToAsk.port)
        result = await self.ping(address, self.sourceNode.id, self.sourceNode.vk)
        return self.handleCallResponse(result, nodeToAsk)

    def welcomeIfNewNode(self, node):
        """
        Add contacts to your routing table
        """
        if not self.router.isNewNode(node):
            return

        log.spam("never seen %s before, adding to router", node)
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

        log.spam("got successful response from %s", node)
        self.welcomeIfNewNode(node)
        return result
