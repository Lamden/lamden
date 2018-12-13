from unittest import TestCase
from cilantro.protocol.structures.capped_containers import CappedDict


class TestCappedDict(TestCase):

    def test_init(self):
        MAX_SIZE = 1260

        rd = CappedDict(max_size=MAX_SIZE)

        self.assertEqual(rd.max_size, MAX_SIZE)

    def test_deletes(self):
        """
        Tests that a rolling dict does not go beyond max size
        """
        MAX_SIZE = 10

        rd = CappedDict(max_size=MAX_SIZE)

        for n in range(MAX_SIZE * 2):
            rd[n] = n

        self.assertTrue(len(rd) <= MAX_SIZE)

    def test_deletes_oldest(self):
        """
        Tests that a rolling dict deletes in FIFO order
        """
        MAX_SIZE = 3

        rd = CappedDict(max_size=MAX_SIZE)

        rd[1] = 1
        rd[2] = 2
        rd[3] = 3
        rd[4] = 4
        rd[5] = 5

        # rolling dict should just have the MAX_SIZE latest values in it
        expected_d = {3: 3, 4: 4, 5: 5}

        self.assertEqual(rd, expected_d)


