from unittest import TestCase
from lamden.nodes.base import Node
import zmq


class TestRollBack(TestCase):
    def setUp(self):
        self.node = Node(
            constitution={},
            ctx=zmq.Context(),
            socket_base='tcp://*:9000',
            wallet=None,
            should_seed=False
        )

    def tearDown(self):
        pass

    def test_add_rollback_info_adds_to_rollback_queue(self):
        self.assertEqual(len(self.node.rollbacks), 0)

        self.node.add_rollback_info()

        self.assertEqual(len(self.node.rollbacks), 1)

    def test_add_rollback_info_returns_info_dict(self):
        r = self.node.add_rollback_info()
        self.assertEqual(list(r.keys()), ['system_time', 'last_processed_hlc', 'last_hlc_in_consensus'])

    def test_add_rollback_info_returns_same_dict_thats_stored(self):
        r = self.node.add_rollback_info()

        self.assertEqual(r, self.node.rollbacks[0])

    def test_add_two_rollbacks_appends_to_list(self):
        r = self.node.add_rollback_info()

        self.assertEqual(r, self.node.rollbacks[0])

        r = self.node.add_rollback_info()

        self.assertEqual(r, self.node.rollbacks[1])

    def test_rollback_drops_database_cache(self):
        self.node.driver.set('test', 'thing1')

        self.assertEqual(self.node.driver.get('test'), 'thing1')

        self.node.rollback_drivers()

        self.assertEqual(self.node.driver.get('test'), None)
