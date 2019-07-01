from unittest import TestCase
from cilantro_ee.protocol.overlay.kademlia.routing import KBucket
from cilantro_ee.protocol.overlay.kademlia.node import Node

class TestKBucket(TestCase):
    def test_init(self):
        k = KBucket(100, 100, 100)
        self.assertEqual(k.range, (100, 100))

    def test_lower_range_higher_than_upper(self):
        with self.assertRaises(AssertionError):
            k = KBucket(101, 100, 100)

    def test_add_node(self):
        n = Node(b'1')
        k = KBucket(0, 1, 2)

        k.add_node(n)

        self.assertEqual(k.nodes[b'1'], n)

    def test_add_node_ksize_maxxed(self):
        n = Node(b'1')
        o = Node(b'2')
        p = Node(b'3')
        k = KBucket(0, 1, 2)

        k.add_node(n)
        k.add_node(o)
        k.add_node(p)

        self.assertEqual(k.nodes[b'1'], n)
        self.assertEqual(k.nodes[b'2'], o)
        self.assertIsNone(k.nodes.get(b'3'))

    def test_add_node_already_exists(self):
        n = Node(b'1', ip='yo')
        o = Node(b'1', ip='no')

        k = KBucket(0, 1, 2)

        k.add_node(n)

        self.assertEqual(k.nodes.get(b'1').ip, 'yo')

        k.add_node(o)

        self.assertEqual(k.nodes.get(b'1').ip, 'no')