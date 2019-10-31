from unittest import TestCase
from cilantro_ee.nodes.delegate.block_manager import SubBlocks
from cilantro_ee.constants.system_config import *
from collections import namedtuple


class TestSubBlocks(TestCase):
    def test_reset_removes_sbs_and_futures(self):
        s = SubBlocks()
        s.sbs = {1, 2, 3}
        s.futures = [1, 2, 3]

        s.reset()

        self.assertEqual(s.sbs, {})
        self.assertEqual(s.futures, [])

    def test_is_quorum_returns_true_if_sbs_equal_num_sb_per_block(self):
        s = SubBlocks()

        s.sbs = {1, 2, 3}
        self.assertTrue(s.is_quorum())

    def test_is_quorum_returns_false_if_sbs_ne_num_sb_per_block(self):
        s = SubBlocks()

        s.sbs = {1, 2}
        self.assertFalse(s.is_quorum())

    def test_add_sub_block_adds_to_proper_index(self):
        MockSB = namedtuple('MockSB', ['subBlockIdx'])

        sb = MockSB(0)

        s = SubBlocks()

        s.add_sub_block(sb, 'something')

        self.assertEqual(s.sbs[0], sb)
        self.assertListEqual(s.futures, ['something'])

    def test_get_sb_hashes_sorted(self):
        MockSB = namedtuple('MockSB', ['resultHash'])

        expected = [6, 7, 8]

        s = SubBlocks()

        s.sbs = [MockSB(6), MockSB(7), MockSB(8)]

        self.assertListEqual(s.get_sb_hashes_sorted(), expected)

    def test_add_and_get_behave_as_expected(self):
        MockSB = namedtuple('MockSB', ['subBlockIdx', 'resultHash'])

        expected = [6, 7, 8]

        s = SubBlocks()

        s.add_sub_block(MockSB(0, 6), 1)
        s.add_sub_block(MockSB(1, 7), 2)
        s.add_sub_block(MockSB(2, 8), 3)

        self.assertListEqual(s.get_sb_hashes_sorted(), expected)

    def test_get_input_hashes_sorted(self):
        MockSB = namedtuple('MockSB', ['inputHash'])

        expected = ['00', '01', '02']

        s = SubBlocks()

        s.sbs = [MockSB(b'\x00'), MockSB(b'\x01'), MockSB(b'\x02')]

        self.assertListEqual(s.get_input_hashes_sorted(), expected)

    def test_get_input_hashes_sorted_works_if_hashes_added(self):
        MockSB = namedtuple('MockSB', ['subBlockIdx', 'inputHash'])

        expected = ['00', '01', '02']

        s = SubBlocks()

        s.add_sub_block(MockSB(0, b'\x00'), 1)
        s.add_sub_block(MockSB(1, b'\x01'), 2)
        s.add_sub_block(MockSB(2, b'\x02'), 3)

        self.assertListEqual(s.get_input_hashes_sorted(), expected)