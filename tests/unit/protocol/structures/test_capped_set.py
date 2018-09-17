from unittest import TestCase
from cilantro.protocol.structures import CappedSet


class TestCappedSet(TestCase):

    def test_init(self):
        MAX_SIZE = 10

        cs = CappedSet(max_size=MAX_SIZE)

        self.assertEqual(cs.max_size, MAX_SIZE)
        self.assertTrue(cs.fifo_queue is not None)

    def test_queue_synced(self):
        """
        Tests that the internal fifo_queue and the set's elements are bijective sets
        """
        MAX_SIZE = 4

        cs = CappedSet(max_size=MAX_SIZE)

        cs.add(1)
        cs.add(2)
        cs.add(3)
        cs.add(4)
        cs.add(5)

        for element in cs.fifo_queue:
            self.assertTrue(element in cs, msg='Element {} not in set {}'.format(element, cs))

    def test_max_size(self):
        """
        Tests that the max size is never exceeded
        """
        MAX_SIZE = 4

        cs = CappedSet(max_size=MAX_SIZE)

        for i in range(10):
            cs.add(i)

        self.assertTrue(len(cs) <= MAX_SIZE)

    def test_overflow(self):
        """
        Tests that the set overflow in FIFO order
        """
        MAX_SIZE = 2

        cs = CappedSet(max_size=MAX_SIZE)

        cs.add(1)
        cs.add(2)
        cs.add(3)

        correct_order = [2, 3]

        for correct, actual in zip(correct_order, cs.fifo_queue):
            self.assertEqual(correct, actual)