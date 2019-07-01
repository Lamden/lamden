import heapq
import time
import operator
import logging

from collections import OrderedDict
from cilantro_ee.constants.overlay_network import *
from cilantro_ee.protocol.overlay.kademlia.node import Node
from cilantro_ee.protocol.overlay.kademlia.utils import digest
from cilantro_ee.protocol.overlay.kademlia.utils import OrderedSet, shared_prefix, bytes_to_bitstring

log = logging.getLogger(__name__)


class KBucket(object):
    def __init__(self, range_lower, range_upper, ksize):
        assert range_lower <= range_upper, 'Lower range cannot be greater than the upper range.'

        self.range = (range_lower, range_upper)

        self.nodes = OrderedDict()

        self.replacementNodes = OrderedSet()
        self.touch_last_updated()
        self.ksize = ksize

    def touch_last_updated(self):
        self.last_updated = time.monotonic()

    def get_nodes(self):
        return list(self.nodes.values())

    def split(self):
        midpoint = (self.range[0] + self.range[1]) / 2
        one = KBucket(self.range[0], midpoint, self.ksize)
        two = KBucket(midpoint + 1, self.range[1], self.ksize)
        for node in self.nodes.values():
            bucket = one if node.long_id <= midpoint else two
            bucket.nodes[node.id] = node
        return (one, two)

    def remove_node(self, node):
        if node.id not in self.nodes:
            return

        # delete node, and see if we can add a replacement
        del self.nodes[node.id]
        if len(self.replacementNodes) > 0:
            new_node = self.replacementNodes.pop()
            self.nodes[new_node.id] = new_node

    def has_in_range(self, node):
        return self.range[0] <= node.long_id <= self.range[1]

    def is_new_node(self, node):
        return node.id not in self.nodes

    def is_full(self):
        return len(self) < self.ksize

    def add_node(self, node):
        """
        Add a C{Node} to the C{KBucket}.  Return True if successful,
        False if the bucket is full.

        If the bucket is full, keep track of node in a replacement list,
        per section 4.1 of the paper.
        """
        if node.id in self.nodes:
            del self.nodes[node.id]
            self.nodes[node.id] = node
        elif len(self) < self.ksize:
            self.nodes[node.id] = node
        else:
            self.replacementNodes.push(node)
            return False
        return True

    # raghu todo - make it simpler with a counter variable in the object and configurable parameter on how deep it can go
    def depth(self):
        vals = self.nodes.values()
        sp = shared_prefix([bytes_to_bitstring(n.id) for n in vals])
        return len(sp)

    def head(self):
        return list(self.nodes.values())[0]

    def __getitem__(self, node_id):
        return self.nodes.get(node_id, None)

    def __len__(self):
        return len(self.nodes)


# raghu todo - experiment with sending only from the bucket, if bucket is empty, then send self node only
class TableTraverser(object):
    def __init__(self, table, start_node):
        index = table.get_bucket_for(start_node)
        table.buckets[index].touch_last_updated()
        self.current_nodes = table.buckets[index].get_nodes()
        self.left_buckets = table.buckets[:index]
        self.right_buckets = table.buckets[(index + 1):]
        self.left = True

    def __iter__(self):
        return self

    def __next__(self):
        """
        Pop an item from the left subtree, then right, then left, etc.
        """
        if len(self.current_nodes) > 0:
            return self.current_nodes.pop()

        if self.left and len(self.left_buckets) > 0:
            self.current_nodes = self.left_buckets.pop().get_nodes()
            self.left = False
            return next(self)

        if len(self.right_buckets) > 0:
            self.current_nodes = self.right_buckets.pop(0).get_nodes()
            self.left = True
            return next(self)

        raise StopIteration


class RoutingTable(object):
    def __init__(self, node):
        """
        @param node: The node that represents this server.  It won't
        be added to the routing table, but will be needed later to
        determine which buckets to split or not.
        """
        self.node = node
        self.ksize = KSIZE
        self.alpha = ALPHA
        # raghu todo - initial num of buckets can be equal to ln(num of nodes)?
        self.buckets = [KBucket(0, 2 ** 160, self.ksize)]
        # raghu todo - make sure the following line can be commented out
        # self.add_contact(node)

    def split_bucket(self, index):
        one, two = self.buckets[index].split()
        self.buckets[index] = one
        self.buckets.insert(index + 1, two)

    def get_lonely_buckets(self):
        """
        Get all of the buckets that haven't been updated in over
        an hour.
        """
        hrago = time.monotonic() - 3600
        return [b for b in self.buckets if b.last_updated < hrago]

    def remove_contact(self, node):
        index = self.get_bucket_for(node)
        self.buckets[index].remove_node(node)

    # raghu todo - this is inefficient serial search. change to binary search
    def is_new_node(self, node):
        index = self.get_bucket_for(node)
        return self.buckets[index].is_new_node(node)

    def add_contact(self, node):
        if node.id == self.node.id:
            return True

        index = self.get_bucket_for(node)
        bucket = self.buckets[index]

        # this will succeed unless the bucket is full
        if bucket.add_node(node):
            return True

        # Per section 4.2 of paper, split if the bucket has the node
        # in its range or if the depth is not congruent to 0 mod 5
        # raghu todo we need to have a reliable way of splitting as well as its control
        if bucket.has_in_range(self.node) or bucket.depth() % 5 != 0:
            self.split_bucket(index)
            self.add_contact(node)
            return True
        return False

    def get_bucket_for(self, node):
        """
        Get the index of the bucket that the given node would fall into.
        """
        for index, bucket in enumerate(self.buckets):
            if node.long_id < bucket.range[1]:
                return index

    def is_vk_in(self, vk):
        node = Node(digest(vk))
        if node.id == self.node.id:
            return self.node
        bucket = self.buckets[self.get_bucket_for(node)]
        return bucket.nodes.get(node.id, None)

    def find_node(self, node):
        k = self.ksize
        if node.id == self.node.id:
            return [self.node]
        bucket = self.buckets[self.get_bucket_for(node)]
        item = bucket.nodes.get(node.id, None)
        if item and node.id == item.id:
            return [item]
        nodes = []
        for neighbor in TableTraverser(self, node):
            nodes.append(neighbor)
            if len(nodes) == k:
                break
        return nodes

    def find_neighbors(self, node, exclude=None):
        bucket = self.buckets[self.get_bucket_for(node)]
        k = max(len(bucket.nodes), self.alpha)
        nodes = []
        for neighbor in TableTraverser(self, node):
            not_excluded = exclude is None or not neighbor.equals(exclude)
            if not_excluded:
                heapq.heappush(nodes, (node.distance_to(neighbor), neighbor))
            if len(nodes) == k:
                break

        return list(map(operator.itemgetter(1), heapq.nsmallest(k, nodes)))

    def get_neighbors(self, node):
        nodes = []
        for neighbor in TableTraverser(self, node):
            nodes.append(neighbor)

        return nodes

    def get_all_connected_vks(self):
        connected_vks = set()
        for bucket in self.buckets:
            for vk in bucket.nodes.keys():
                connected_vks.add(vk)
        return connected_vks

    def num_contacts(self):
        num_nodes = 0
        for bucket in self.buckets:
            num_nodes += len(bucket.nodes)
        return num_nodes

    def get_my_neighbors(self):
        return self.get_neighbors(self.node)

    def get_num_buckets(self):
        return len(self.buckets)
