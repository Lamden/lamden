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

    def test_split_creates_two_buckets_with_proper_nodes_in_each(self):
        # Nodes are sorted by long IDs, which are just integers of the ID provided.
        # Node IDs are bytes

        n1 = Node(node_id=b'0')  # 48
        n2 = Node(node_id=b'1')  # 49
        n3 = Node(node_id=b'2')  # 50
        n4 = Node(node_id=b'3')  # 51
        n5 = Node(node_id=b'4')  # 52

        bucket = KBucket(48, 52, 10)

        bucket.add_node(n1)
        bucket.add_node(n2)
        bucket.add_node(n3)
        bucket.add_node(n4)
        bucket.add_node(n5)

        lesser_bucket, greater_bucket = bucket.split()

        lesser_nodes = list(lesser_bucket.nodes.values())
        self.assertEqual(lesser_nodes, [n1, n2, n3])

        greater_nodes = list(greater_bucket.nodes.values())
        self.assertEqual(greater_nodes, [n4, n5])

    def test_adding_nodes_over_ksize_puts_them_in_replacement_nodes(self):
        n1 = Node(node_id=b'0')  # 48
        n2 = Node(node_id=b'1')  # 49
        n3 = Node(node_id=b'2')  # 50
        n4 = Node(node_id=b'3')  # 51
        n5 = Node(node_id=b'4')  # 52

        bucket = KBucket(48, 52, 2)

        res_1 = bucket.add_node(n1)
        res_2 = bucket.add_node(n2)
        res_3 = bucket.add_node(n3)
        res_4 = bucket.add_node(n4)
        res_5 = bucket.add_node(n5)

        self.assertEqual(bucket.replacement_nodes, [n3, n4, n5])
        self.assertEqual([res_1, res_2, res_3, res_4, res_5], [True, True, False, False, False])

    def test_get_nodes_returns_an_ordered_list(self):
        n1 = Node(node_id=b'0')  # 48
        n2 = Node(node_id=b'1')  # 49
        n3 = Node(node_id=b'2')  # 50
        n4 = Node(node_id=b'3')  # 51
        n5 = Node(node_id=b'4')  # 52

        bucket = KBucket(48, 52, 10)

        bucket.add_node(n1)
        bucket.add_node(n2)
        bucket.add_node(n3)
        bucket.add_node(n4)
        bucket.add_node(n5)

        self.assertEqual(bucket.get_nodes(), [n1, n2, n3, n4, n5])

    def test_remove_node_does_nothing_if_node_doesnt_exist(self):
        n1 = Node(node_id=b'0')  # 48
        n2 = Node(node_id=b'1')  # 49
        n3 = Node(node_id=b'2')  # 50
        n4 = Node(node_id=b'3')  # 51
        n5 = Node(node_id=b'4')  # 52

        bucket = KBucket(48, 52, 10)

        bucket.add_node(n1)
        bucket.add_node(n2)
        bucket.add_node(n3)
        bucket.add_node(n4)
        bucket.add_node(n5)

        test_node = Node(node_id=b'999')

        bucket.remove_node(test_node)

        self.assertEqual(bucket.get_nodes(), [n1, n2, n3, n4, n5])

    def test_remove_node_removes_the_node_if_it_exists(self):
        n1 = Node(node_id=b'0')  # 48
        n2 = Node(node_id=b'1')  # 49
        n3 = Node(node_id=b'2')  # 50
        n4 = Node(node_id=b'3')  # 51
        n5 = Node(node_id=b'4')  # 52

        bucket = KBucket(48, 52, 10)

        bucket.add_node(n1)
        bucket.add_node(n2)
        bucket.add_node(n3)
        bucket.add_node(n4)
        bucket.add_node(n5)

        test_node = Node(node_id=b'3')

        bucket.remove_node(test_node)

        self.assertEqual(bucket.get_nodes(), [n1, n2, n3, n5])

    def test_remove_node_adds_a_replacement_node_if_one_exists(self):
        n1 = Node(node_id=b'0')  # 48
        n2 = Node(node_id=b'1')  # 49
        n3 = Node(node_id=b'2')  # 50
        n4 = Node(node_id=b'3')  # 51
        n5 = Node(node_id=b'4')  # 52
        n6 = Node(node_id=b'5')

        bucket = KBucket(48, 54, 5)

        bucket.add_node(n1)
        bucket.add_node(n2)
        bucket.add_node(n3)
        bucket.add_node(n4)
        bucket.add_node(n5)
        bucket.add_node(n6)

        test_node = Node(node_id=b'3')

        bucket.remove_node(test_node)

        self.assertEqual(bucket.get_nodes(), [n1, n2, n3, n5, n6])

    def test_depth(self):
        n1 = Node(node_id=b'0')  # 48
        n2 = Node(node_id=b'1')  # 49
        n3 = Node(node_id=b'2')  # 50
        n4 = Node(node_id=b'3')  # 51
        n5 = Node(node_id=b'4')  # 52
        n6 = Node(node_id=b'5')

        bucket = KBucket(48, 54, 5)

        bucket.add_node(n1)
        bucket.add_node(n2)
        bucket.add_node(n3)
        bucket.add_node(n4)
        bucket.add_node(n5)
        bucket.add_node(n6)

        self.assertEqual(bucket.depth(), 5)

    def test_depth_but_wide(self):
        n1 = Node(node_id=b'ag')  # 48
        n2 = Node(node_id=b'gggggggg')  # 49
        n3 = Node(node_id=b'223')  # 50
        n4 = Node(node_id=b'3gde')  # 51
        n5 = Node(node_id=b'400000')  # 52

        bucket = KBucket(48, 54, 5)

        bucket.add_node(n1)
        bucket.add_node(n2)
        bucket.add_node(n3)
        bucket.add_node(n4)
        bucket.add_node(n5)

        self.assertEqual(bucket.depth(), 0)

    def test_bucket_has_in_range_true(self):
        n = Node(node_id=b'4')  # 52

        bucket = KBucket(48, 52, 5)

        self.assertTrue(bucket.has_in_range(n))

    def test_bucket_has_in_range_false(self):
        n = Node(node_id=b'4')  # 52

        bucket = KBucket(48, 51, 5)

        self.assertFalse(bucket.has_in_range(n))

    def test_bucket_is_new_node_true(self):
        n1 = Node(node_id=b'0')  # 48
        n2 = Node(node_id=b'1')  # 49

        bucket = KBucket(48, 54, 5)

        bucket.add_node(n1)

        self.assertTrue(bucket.is_new_node(n2))

    def test_bucket_is_new_node_false(self):
        n1 = Node(node_id=b'0')  # 48
        n2 = Node(node_id=b'1')  # 49

        bucket = KBucket(48, 54, 5)

        bucket.add_node(n1)
        bucket.add_node(n2)

        self.assertFalse(bucket.is_new_node(n2))

    def test_bucket_is_full_true(self):
        n1 = Node(node_id=b'0')  # 48
        n2 = Node(node_id=b'1')  # 49
        n3 = Node(node_id=b'2')  # 50
        n4 = Node(node_id=b'3')  # 51
        n5 = Node(node_id=b'4')  # 52

        bucket = KBucket(48, 54, 5)

        bucket.add_node(n1)
        bucket.add_node(n2)
        bucket.add_node(n3)
        bucket.add_node(n4)
        bucket.add_node(n5)

        self.assertTrue(bucket.is_full())

    def test_bucket_is_full_false(self):
        n1 = Node(node_id=b'0')  # 48
        n2 = Node(node_id=b'1')  # 49
        n3 = Node(node_id=b'2')  # 50
        n4 = Node(node_id=b'3')  # 51

        bucket = KBucket(48, 54, 5)

        bucket.add_node(n1)
        bucket.add_node(n2)
        bucket.add_node(n3)
        bucket.add_node(n4)

        self.assertFalse(bucket.is_full())

    def test_bucket_get_item(self):
        n1 = Node(node_id=b'0')  # 48
        n2 = Node(node_id=b'1')  # 49
        n3 = Node(node_id=b'2')  # 50
        n4 = Node(node_id=b'3')  # 51

        bucket = KBucket(48, 54, 5)

        bucket.add_node(n1)
        bucket.add_node(n2)
        bucket.add_node(n3)
        bucket.add_node(n4)

        self.assertEqual(bucket[b'3'], n4)

    def test_bucket_get_head(self):
        n1 = Node(node_id=b'0')  # 48
        n2 = Node(node_id=b'1')  # 49
        n3 = Node(node_id=b'2')  # 50
        n4 = Node(node_id=b'3')  # 51

        bucket = KBucket(48, 54, 5)

        bucket.add_node(n1)
        bucket.add_node(n2)
        bucket.add_node(n3)
        bucket.add_node(n4)

        self.assertEqual(bucket.head(), n1)