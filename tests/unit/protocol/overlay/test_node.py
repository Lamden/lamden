from unittest import TestCase
from cilantro_ee.protocol.overlay.kademlia.node import Node, NodeHeap


class TestNode(TestCase):
    def test_init(self):
        n = Node(b'0')

    def test_iter(self):
        args = [b'0', b'1.1.1.1', b'100', b'sdf']
        n = Node(*args)

        self.assertEqual(list(n), args)

    def test_same_home_as_node_true(self):
        args_1 = [b'0', b'1.1.1.1', b'100', b'sdf']
        args_2 = [b'0', b'1.1.1.1', b'100', b'sdf']

        n = Node(*args_1)
        o = Node(*args_2)

        self.assertTrue(n.same_home_as(o))

    def test_same_home_as_node_true_different_id(self):
        args_1 = [b'1', b'1.1.1.1', b'100', b'sdf']
        args_2 = [b'0', b'1.1.1.1', b'100', b'sdf']

        n = Node(*args_1)
        o = Node(*args_2)

        self.assertTrue(n.same_home_as(o))

    def test_same_home_as_node_false_ip(self):
        args_1 = [b'0', b'1.1.1.0', b'100', b'sdf']
        args_2 = [b'0', b'1.1.1.1', b'100', b'sdf']

        n = Node(*args_1)
        o = Node(*args_2)

        self.assertFalse(n.same_home_as(o))

    def test_same_home_as_node_false_port(self):
        args_1 = [b'0', b'1.1.1.1', b'101', b'sdf']
        args_2 = [b'0', b'1.1.1.1', b'100', b'sdf']

        n = Node(*args_1)
        o = Node(*args_2)

        self.assertFalse(n.same_home_as(o))

    def test_same_home_as_node_false_vk(self):
        args_1 = [b'0', b'1.1.1.1', b'100', b'sdF']
        args_2 = [b'0', b'1.1.1.1', b'100', b'sdf']

        n = Node(*args_1)
        o = Node(*args_2)

        self.assertFalse(n.same_home_as(o))

    def test_long_id_properly_created(self):
        _id = b'1'

        n = Node(_id)

        self.assertEqual(n.long_id, int(_id.hex(), 16))

    def test_distance_to(self):
        id_1 = int(b'1'.hex(), 16)
        id_2 = int(b'2'.hex(), 16)

        n = Node(b'1')
        y = Node(b'2')

        self.assertEqual(n.distance_to(y), id_1 ^ id_2)


class TestNodeHeap(TestCase):
    def test_init(self):
        n = Node(b'1')
        h = NodeHeap(n, 100)

    def test_push_node(self):
        a = Node(b'1')
        b = Node(b'2')

        h = NodeHeap(a, 100)

        h.push(b)

