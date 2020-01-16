from unittest import TestCase
from cilantro_ee.nodes.delegate.sub_block_builder_manager import SubBlocks, NextBlockData, NextBlock
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


class MockBlock:
    def which(self):
        return 'SomethingElse'


class MockFailedBlock:
    def which(self):
        return 'FailedBlock'


class TestNextBlockData(TestCase):
    def test_init_non_failed_block_inits_quorum_num(self):
        n = NextBlockData(MockBlock())

        self.assertEqual(n.quorum_num, BLOCK_NOTIFICATION_QUORUM)

    def test_init_failed_block_inits_quorum_num(self):
        n = NextBlockData(MockFailedBlock())

        self.assertEqual(n.quorum_num, FAILED_BLOCK_NOTIFICATION_QUORUM)

    def test_add_sender_returns_false_if_is_quorum(self):
        n = NextBlockData(MockBlock())

        n.is_quorum = True

        self.assertFalse(n.add_sender(1))

    def test_add_sender_returns_false_if_senders_lte_quorum_num(self):
        n = NextBlockData(MockBlock())

        self.assertFalse(n.add_sender(1))

    def test_add_sender_returns_true_if_not_quorum_and_senders_gte_quorum_num(self):
        n = NextBlockData(MockBlock())

        self.assertFalse(n.add_sender(1))
        self.assertTrue(n.add_sender(2))

    def test_add_sender_returns_false_if_quorum_after_adding_senders(self):
        n = NextBlockData(MockBlock())

        self.assertFalse(n.add_sender(1))
        self.assertTrue(n.add_sender(2))
        self.assertFalse(n.add_sender(3))


class TestNextBlock(TestCase):
    def test_hard_reset_resets_state(self):
        n = NextBlock()
        n.next_block_data = {1, 2, 3}
        n.quorum_block = 1
        n.hard_reset()

        self.assertEqual(n.next_block_data, {})
        self.assertEqual(n.quorum_block, None)

    def test_reset_greater_than_existing_block_removes_block_from_set(self):
        n = NextBlock()

        MockBlock = namedtuple('MockBlock', ['blockNum'])

        n.quorum_block = MockBlock(0)
        n.next_block_data[0] = 123

        n.reset(1)

        self.assertIsNone(n.quorum_block)
        self.assertIsNone(n.next_block_data.get(0))

    def test_reset_less_than_existing_block_does_not_remove_next_block_but_removes_quorum_block(self):
        n = NextBlock()

        MockBlock = namedtuple('MockBlock', ['blockNum'])

        n.quorum_block = MockBlock(0)
        n.next_block_data[0] = 123

        n.reset(0)

        self.assertIsNone(n.quorum_block)
        self.assertEqual(n.next_block_data.get(0), 123)

    def test_is_quorum_returns_true_if_quorum_block(self):
        n = NextBlock()

        n.quorum_block = 1

        self.assertTrue(n.is_quorum())

    def test_is_quorum_returns_false_if_not_quorum_block(self):
        n = NextBlock()

        self.assertFalse(n.is_quorum())

    def test_add_notification_returns_false_if_quorum_block_and_block_num_matches_arg(self):
        n = NextBlock()

        MockBlock = namedtuple('MockBlock', ['blockNum'])

        n.quorum_block = MockBlock(999)

        self.assertFalse(n.add_notification(None, None, 999, None))

    def test_add_notification_makes_empty_hash_if_block_num_not_in_next_block_data_and_adds_data(self):
        n = NextBlock()

        self.assertIsNone(n.next_block_data.get(999))

        m = MockBlock()

        n.add_notification(m, None, 999, None)

        self.assertEqual(n.next_block_data[999][None].block_notif, m)

    def test_add_notification_returns_false_if_not_add_sender(self):
        n = NextBlock()

        m = MockBlock()

        self.assertFalse(n.add_notification(m, None, 999, None))

    def test_add_notification_returns_true_if_add_sender_returns_true(self):
        n = NextBlock()

        m = MockBlock()

        n.add_notification(m, 1, 999, None)
        self.assertTrue(n.add_notification(m, 2, 999, None))

    def test_add_notification_returns_true_if_add_sender_true_and_sets_quorum_block_to_notif(self):
        n = NextBlock()

        m = MockBlock()

        n.add_notification(m, 1, 999, None)
        n.add_notification(m, 2, 999, None)

        self.assertEqual(n.quorum_block, m)