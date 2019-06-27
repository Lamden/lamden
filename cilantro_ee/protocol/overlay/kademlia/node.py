from operator import itemgetter
import heapq

class Node:
    def __init__(self, node_id: bytes, ip=None, port=None, vk=None):
        self.id = node_id
        self.ip = ip
        self.port = port
        self.long_id = int(node_id.hex(), 16)
        self.vk = vk

    def same_home_as(self, node):
        return self.ip == node.ip and self.port == node.port and self.vk == node.vk

    def distance_to(self, node):
        """
        Get the distance between this node and another.
        """
        return self.long_id ^ node.long_id

    def __iter__(self):
        """
        Enables use of Node as a tuple - i.e., tuple(node) works.
        """
        return iter([self.id, self.ip, self.port, self.vk])

    def __repr__(self):
        return repr([self.long_id, self.ip, self.port, self.vk])

    def __str__(self):
        return "%s:%s:%s" % (self.ip, str(self.port), self.vk)
