import unittest, cilantro
from unittest import TestCase
from cilantro.protocol.overlay.node import *
from os.path import exists, dirname

import unittest
import random
import hashlib

from cilantro.utils.test.overlay import *


class NodeTest(unittest.TestCase):
    def test_longID(self):
        rid = hashlib.sha1(str(random.getrandbits(255)).encode()).digest()
        n = Node(rid)
        self.assertEqual(n.long_id, int(rid.hex(), 16))

    def test_distanceCalculation(self):
        ridone = hashlib.sha1(str(random.getrandbits(255)).encode())
        ridtwo = hashlib.sha1(str(random.getrandbits(255)).encode())

        shouldbe = int(ridone.hexdigest(), 16) ^ int(ridtwo.hexdigest(), 16)
        none = Node(ridone.digest())
        ntwo = Node(ridtwo.digest())
        self.assertEqual(none.distanceTo(ntwo), shouldbe)

    def test_node(self):
        a = Node(node_id=b'aaaa', ip='1.2.3.4', port=8080)
        b = Node(node_id=b'bbbb', ip='1.2.3.4', port=8080)
        self.assertTrue(a.sameHomeAs(b))
        self.assertIsNotNone(iter(a))
        self.assertIsNotNone(repr(b))
        self.assertIsNotNone(str(a))

class NodeHeapTest(unittest.TestCase):
    def test_maxSize(self):
        n = NodeHeap(mknode(intid=0), 3)
        self.assertEqual(0, len(n))

        for d in range(10):
            n.push(mknode(intid=d))
        self.assertEqual(3, len(n))

        self.assertEqual(3, len(list(n)))

    def test_iteration(self):
        heap = NodeHeap(mknode(intid=0), 5)
        nodes = [mknode(intid=x) for x in range(10)]
        for index, node in enumerate(nodes):
            heap.push(node)
        for index, node in enumerate(heap):
            self.assertEqual(index, node.long_id)
            self.assertTrue(index < 5)

    def test_remove(self):
        heap = NodeHeap(mknode(intid=0), 5)
        nodes = [mknode(intid=x) for x in range(10)]
        for node in nodes:
            heap.push(node)
        heap.remove([nodes[0].id, nodes[1].id])
        self.assertEqual(len(list(heap)), 5)
        for index, node in enumerate(heap):
            self.assertEqual(index + 2, node.long_id)
        self.assertTrue(index < 5)

        heap.remove([])

    def test_getNodeById(self):
        heap = NodeHeap(mknode(node_id=b'0', ip='1.2.3.4', port=1234), 5)
        nodes = [mknode(node_id=str(x).encode(), ip='1.2.3.{}'.format(x), port=1234) for x in range(10)]
        for node in nodes:
            heap.push(node)
        node = heap.getNodeById(b'7')
        self.assertTrue(node in heap)
        self.assertIsInstance(node, Node)
        self.assertEqual(node.id, b'7')
        self.assertEqual(node.ip, '1.2.3.7')
        self.assertEqual(node.port, 1234)
        node = heap.getNodeById(b'123')
        self.assertFalse(mknode(intid=0) in heap)
        self.assertIsNone(node)
        self.assertEqual(heap.getIDs(), [b'0', b'1', b'2', b'3', b'4']) # because of maxsize


    def test_contacts(self):
        heap = NodeHeap(mknode(intid=0), 5)
        nodes = [mknode(intid=x) for x in range(4)]
        for node in nodes:
            heap.push(node)
            heap.markContacted(node)
        self.assertTrue(heap.allBeenContacted())
        for n in range(4):
            node = heap.popleft()
            self.assertIsNotNone(node)
        self.assertIsNone(heap.popleft())


if __name__ == '__main__':
    unittest.main()
