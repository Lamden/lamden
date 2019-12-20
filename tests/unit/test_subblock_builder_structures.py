from unittest import TestCase
from cilantro_ee.nodes.delegate.sub_block_builder_manager import SubBlockHandler, BlockNotifData, BlockNotifHandler
from cilantro_ee.constants.system_config import *
from collections import namedtuple


class TestSubBlocks(TestCase):
    def test_reset_removes_sbs(self):
        s = SubBlockHandler(num_sb_per_block=3)
        s.sbs = {1, 2, 3}
        s.futures = [1, 2, 3]

        s.reset()

        self.assertEqual(s.sbs, {})

    def test_is_quorum_returns_true_if_sbs_equal_num_sb_per_block(self):
        s = SubBlockHandler(num_sb_per_block=3)

        s.sbs = {1, 2, 3}
        self.assertTrue(s.is_quorum())

    def test_is_quorum_returns_false_if_sbs_ne_num_sb_per_block(self):
        s = SubBlockHandler(num_sb_per_block=3)

        s.sbs = {1, 2}
        self.assertFalse(s.is_quorum())

    def test_add_sub_block_adds_to_proper_index(self):
        MockSB = namedtuple('MockSB', ['subBlockNum'])

        sb = MockSB(0)

        s = SubBlockHandler(num_sb_per_block=3)

        s.add_sub_block(sb)

        self.assertEqual(s.sbs[0], sb)

    def test_get_sb_hashes_sorted(self):
        MockSB = namedtuple('MockSB', ['resultHash'])

        expected = [6, 7, 8]

        s = SubBlockHandler(num_sb_per_block=3)

        s.sbs = [MockSB(6), MockSB(7), MockSB(8)]

        self.assertListEqual(s.get_sb_hashes_sorted(), expected)

    def test_add_and_get_behave_as_expected(self):
        MockSB = namedtuple('MockSB', ['subBlockNum', 'resultHash'])

        expected = [6, 7, 8]

        s = SubBlockHandler(num_sb_per_block=3)

        s.add_sub_block(MockSB(0, 6))
        s.add_sub_block(MockSB(1, 7))
        s.add_sub_block(MockSB(2, 8))

        self.assertListEqual(s.get_sb_hashes_sorted(), expected)

    def test_get_input_hashes_sorted(self):
        MockSB = namedtuple('MockSB', ['inputHash'])

        expected = ['00', '01', '02']

        s = SubBlockHandler(num_sb_per_block=3)

        s.sbs = [MockSB(b'\x00'), MockSB(b'\x01'), MockSB(b'\x02')]

        self.assertListEqual(s.get_input_hashes_sorted(), expected)

    def test_get_input_hashes_sorted_works_if_hashes_added(self):
        MockSB = namedtuple('MockSB', ['subBlockNum', 'inputHash'])

        expected = ['00', '01', '02']

        s = SubBlockHandler(num_sb_per_block=3)

        s.add_sub_block(MockSB(0, b'\x00'))
        s.add_sub_block(MockSB(1, b'\x01'))
        s.add_sub_block(MockSB(2, b'\x02'))

        self.assertListEqual(s.get_input_hashes_sorted(), expected)


class MockBaseBlock:
    def __init__(self, block_num=1, block_hash='x'):
        self.blockNum = block_num
        self.blockHash = block_hash


class MockBlock(MockBaseBlock):
    def __init__(self, block_num=1, block_hash='x'):
        super().__init__(block_num, block_hash)

    def which(self):
        return 'SomethingElse'


class MockFailedBlock(MockBaseBlock):
    def __init__(self, block_num=1, block_hash='x'):
        super().__init__(block_num, block_hash)

    def which(self):
        return 'FailedBlock'


class TestNextBlockData(TestCase):
    def test_init_non_failed_block_inits_quorum_num(self):
        n = BlockNotifData(MockBlock(), bn_quorum=10, fbn_quorum=5)

        self.assertEqual(n.quorum_num, 10)

    def test_init_failed_block_inits_quorum_num(self):
        n = BlockNotifData(MockFailedBlock(), bn_quorum=10, fbn_quorum=1)

        self.assertEqual(n.quorum_num, 1)

    def test_add_sender_returns_false_if_is_quorum(self):
        n = BlockNotifData(MockBlock(), bn_quorum=10, fbn_quorum=5)

        n.is_quorum = True

        self.assertFalse(n.add_sender(1))

    def test_add_sender_returns_false_if_senders_lte_quorum_num(self):
        n = BlockNotifData(MockBlock(), bn_quorum=1, fbn_quorum=1)

        self.assertTrue(n.add_sender(12))
        self.assertFalse(n.add_sender(0))

    def test_add_sender_returns_true_if_not_quorum_and_senders_gte_quorum_num(self):
        n = BlockNotifData(MockBlock(), bn_quorum=2, fbn_quorum=5)

        self.assertFalse(n.add_sender(1))
        self.assertTrue(n.add_sender(2))

    def test_add_sender_returns_false_if_quorum_after_adding_senders(self):
        n = BlockNotifData(MockBlock(), bn_quorum=2, fbn_quorum=5)

        self.assertFalse(n.add_sender(1))
        self.assertTrue(n.add_sender(2))
        self.assertFalse(n.add_sender(3))


class TestNextBlock(TestCase):
    def test_hard_reset_resets_state(self):
        n = BlockNotifHandler(num_masters=1)
        n.block_notif_data = {1, 2, 3}
        n.quorum_block = 1
        n.hard_reset()

        self.assertEqual(n.block_notif_data, {})
        self.assertEqual(n.quorum_block, None)

    def test_reset_greater_than_existing_block_removes_block_from_set(self):
        n = BlockNotifHandler(1)

        MockBlock = namedtuple('MockBlock', ['blockNum'])

        n.quorum_block = MockBlock(0)
        n.block_notif_data[0] = 123

        n.reset(1)

        self.assertIsNone(n.quorum_block)
        self.assertIsNone(n.block_notif_data.get(0))

    def test_reset_less_than_existing_block_does_not_remove_next_block_but_removes_quorum_block(self):
        n = BlockNotifHandler(1)

        MockBlock = namedtuple('MockBlock', ['blockNum'])

        n.quorum_block = MockBlock(0)
        n.block_notif_data[0] = 123

        n.reset(0)

        self.assertIsNone(n.quorum_block)
        self.assertEqual(n.block_notif_data.get(0), 123)

    def test_is_quorum_returns_true_if_quorum_block(self):
        n = BlockNotifHandler(1)

        n.quorum_block = 1

        self.assertTrue(n.is_quorum())

    def test_is_quorum_returns_false_if_not_quorum_block(self):
        n = BlockNotifHandler(1)

        self.assertFalse(n.is_quorum())

    def test_add_notification_returns_false_if_quorum_block_and_block_num_matches_arg(self):
        n = BlockNotifHandler(3)

        n.quorum_block = MockBlock(3)

        self.assertFalse(n.add_notification(MockBlock(), None))

    def test_add_notification_makes_empty_hash_if_block_num_not_in_next_block_data_and_adds_data(self):
        n = BlockNotifHandler(1)

        self.assertIsNone(n.block_notif_data.get(1))

        m = MockBlock()

        n.add_notification(m, 1)

        self.assertEqual(n.block_notif_data[1]['x'].block_notif, m)

    def test_add_notification_returns_false_if_not_add_sender(self):
        n = BlockNotifHandler(3)

        m = MockBlock()

        self.assertFalse(n.add_notification(m, None))

    def test_add_notification_returns_true_if_add_sender_returns_true(self):
        n = BlockNotifHandler(3)

        m = MockBlock()

        n.add_notification(m, 1)
        self.assertTrue(n.add_notification(m, 2))

    def test_add_notification_returns_true_if_add_sender_true_and_sets_quorum_block_to_notif(self):
        n = BlockNotifHandler(1)

        m = MockBlock()

        n.add_notification(m, 1)
        n.add_notification(m, 2)

        self.assertEqual(n.quorum_block, m)
