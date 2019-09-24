from unittest import TestCase
from cilantro_ee.core.sockets import MasternodeSockets, SocketBook
import zmq


class TestSocketBook(TestCase):
    def test_new_nodes(self):
        current_nodes = {1, 2, 3, 4}
        all_nodes = {1, 2, 3, 4, 5, 6, 7, 8}

        self.assertEqual(SocketBook.new_nodes(all_nodes, current_nodes), {5, 6, 7, 8})

    def test_old_nodes(self):
        current_nodes = {1, 2, 3, 4}
        all_nodes = {1, 2, 3, 4, 5, 6, 7, 8}

        self.assertEqual(SocketBook.old_nodes(all_nodes, current_nodes), set())

    def test_old_nodes_actual_difference(self):
        current_nodes = {1, 2, 3, 4}
        all_nodes = {1, 4, 5, 6, 7, 8}

        self.assertEqual(SocketBook.old_nodes(all_nodes, current_nodes), {2, 3})

    def test_remove_node(self):
        m = SocketBook()
        ctx = zmq.Context()
        m.sockets = {'a': ctx.socket(zmq.PUB), 'b': ctx.socket(zmq.PUB)}

        m.remove_node('a')

        self.assertIsNone(m.sockets.get('a'))
        self.assertIsNotNone(m.sockets.get('b'))

