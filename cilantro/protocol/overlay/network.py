from sklearn.known_nodes import KDTree
from cilantro.constants.ports import *
from cilantro.protocol.overlay.ip import ip_to_decimal
from cilantro.utils import lazy_property
import numpy as np

class Node:
    def __init__(self, ip, vk, coor=[0, 0]):
        self.nodeid = ip_to_decimal(ip)
        self.ip = ip
        self.vk = vk
        self.coor = coor

    @lazy_property
    def tree_item(self):
        # TODO normalize geo coordinates and nodeid
        return [self.nodeid]

    def __repr__(self):
        return '<Node ip={}, vk={}, coor={}>'.format(self.ip, self.vk, self.coor)

class Network:

    neighbors = {} # Direct neighbors
    known_nodes = {} # Similar to KBuckets
    X = np.array([])
    port = NETWORK_PORT

    @classmethod
    def update_distance_tree(cls, new_nodes):
        cls.known_nodes.update(new_nodes)
        cls.X = np.array([cls.known_nodes[nodeid].tree_item for nodeid in cls.known_nodes])
        cls.kdt = KDTree(cls.X, leaf_size=30, metric='euclidean')

    @classmethod
    def get_closest_n_known_nodes(cls, node, limit=4):
        dist, ind = cls.kdt.query([node.tree_item], k=limit, return_distance=True, sort_results=True)
        return [
            cls.known_nodes[item[0]] \
            for item in [cls.X[i] for i in ind][0]
        ]

    @classmethod
    def bootstrap(cls):
        
        pass

node1 = Node('127.0.0.1', 'abcd1', [2,3])
node2 = Node('127.0.0.2', 'abcd2', [3,3])
node3 = Node('127.0.0.3', 'abcd3', [3,4])
node4 = Node('127.0.0.4', 'abcd4', [3,2])
node5 = Node('127.0.0.5', 'abcd5', [4,2])

Network.update_distance_tree({
    node.nodeid: node \
    for node in [node1, node2, node3, node4, node5]
})
print(Network.get_closest_n_known_nodes(node2, limit=2))
