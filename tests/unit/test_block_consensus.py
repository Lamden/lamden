from unittest import TestCase

import asyncio
import os
import shutil

from lamden.nodes.processors.block_consensus import BlockConsensus
from lamden.storage import BlockStorage

class TestBlockConsensus(TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.test_dir = os.path.abspath('./.lamden')

        self.create_directories()

        self.block_storage = BlockStorage(root=self.test_dir)

        self.block_consensus = BlockConsensus(
            block_storage=self.block_storage
        )

    def tearDown(self):
        try:
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.close()
        except RuntimeError:
            pass

    def create_directories(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

        os.makedirs(self.test_dir)

    def test_INSTANCE__can_create_instance(self):
        block_consensus = BlockConsensus(
            block_storage=self.block_storage
        )
        self.assertIsInstance(block_consensus, BlockConsensus)

    def test_PRIVATE_METHOD_get_required_consensus__returns_51_percent_of_member_count(self):
        self.block_consensus.member_counts[10] = 10
        self.block_consensus.member_counts[20] = 20
        self.block_consensus.member_counts[30] = 30

        required_consensus = self.block_consensus._get_required_consensus(block_num=20)

        self.assertEqual(11, required_consensus)

    def test_PRIVATE_METHOD_get_required_consensus__returns_1_if_not_found(self):
        required_consensus = self.block_consensus._get_required_consensus(block_num=20)

        self.assertEqual(1, required_consensus)

    def test_PRIVATE_METHOD_cleanup__removes_past_and_current_entries(self):
        self.block_consensus.validation_height = 2

        # past
        self.block_consensus.pending_blocks[1] = True
        self.block_consensus.minted_blocks[1] = True
        self.block_consensus.member_counts[1] = True

        # current
        self.block_consensus.pending_blocks[2] = True
        self.block_consensus.minted_blocks[2] = True
        self.block_consensus.member_counts[2] = True

        self.block_consensus._cleanup()

        self.assertIsNone(self.block_consensus.pending_blocks.get(1))
        self.assertIsNone(self.block_consensus.minted_blocks.get(1))
        self.assertIsNone(self.block_consensus.member_counts.get(1))

        self.assertIsNone(self.block_consensus.pending_blocks.get(2))
        self.assertIsNone(self.block_consensus.minted_blocks.get(2))
        self.assertIsNone(self.block_consensus.member_counts.get(2))

    def test_PRIVATE_METHOD_cleanup__keeps_future_entries(self):
        self.block_consensus.validation_height = 2

        # future
        self.block_consensus.pending_blocks[3] = True
        self.block_consensus.minted_blocks[3] = True
        self.block_consensus.member_counts[3] = True

        self.block_consensus._cleanup()

        self.assertTrue(self.block_consensus.pending_blocks.get(3))
        self.assertTrue(self.block_consensus.minted_blocks.get(3))
        self.assertTrue(self.block_consensus.member_counts.get(3))

    def test_PRIVATE_METHOD_populate_member_count__looks_up_member_count_if_does_not_exist(self):
        self.block_storage.member_history.set(block_num='10', members_list=['jeff', 'stu', 'archer', 'olver', 'greg'])

        self.assertIsNone(self.block_consensus.member_counts.get(10))

        self.block_consensus._populate_member_count(block_num=10)

        self.assertIsNotNone(self.block_consensus.member_counts.get(10))

    def test_PRIVATE_METHOD_populate_member_count__does_not_set_if_exists(self):
        # give it a member count
        self.block_consensus.member_counts[10] = 10

        # set a different member count in the driver
        self.block_storage.member_history.set(block_num='10', members_list=['jeff', 'stu', 'archer', 'olver', 'greg'])

        self.block_consensus._populate_member_count(block_num=10)

        # should have not changed the value
        self.assertEqual(10, self.block_consensus.member_counts.get(10))

    def test_PRIVATE_METHOD_validate_block__returns_if_block_num_less_than_or_eq_valid_height(self):
        self.block_consensus.validation_height = 10

        res = self.block_consensus._validate_block(block_num=9, block_hash='abc')

        self.assertEqual('earlier', res)

    def test_PRIVATE_METHOD_validate_block__returns_None_if_not_enough_to_do_consensus(self):
        self.block_consensus.member_counts[10] = 4
        self.block_consensus.validation_height = 9
        res = self.block_consensus._validate_block(block_num=10, block_hash='abc')

        self.block_consensus.pending_blocks[10] = ['abc', 'abc', 'abc']

        self.assertIsNone(res)

    def test_PRIVATE_METHOD_validate_block__returns_True_if_has_consensus_and_I_match(self):
        self.block_consensus.member_counts[10] = 2
        self.block_consensus.minted_blocks[10] = 'abc'
        self.block_consensus.validation_height = 9

        self.block_consensus.pending_blocks[10] = ['abc', 'abc', 'abc']

        res = self.block_consensus._validate_block(block_num=10, block_hash='abc')

        self.assertTrue(res)

    def test_PRIVATE_METHOD_validate_block__returns_False_if_has_consensus_and_I_do_not_match(self):
        self.block_consensus.member_counts[10] = 2
        self.block_consensus.minted_blocks[10] = 'def'
        self.block_consensus.validation_height = 9

        self.block_consensus.pending_blocks[10] = ['abc', 'abc', 'abc']

        res = self.block_consensus._validate_block(block_num=10, block_hash='abc')

        self.assertFalse(res)

    def test_PRIVATE_METHOD_validate_block__returns_None_if_has_consensus_but_I_have_no_result(self):
        self.block_consensus.member_counts[10] = 2
        self.block_consensus.validation_height = 9

        self.block_consensus.pending_blocks[10] = ['abc', 'abc', 'abc']

        res = self.block_consensus._validate_block(block_num=10, block_hash='abc')

        self.assertFalse(res)

    def test_PRIVATE_METHOD_validate_block__returns_None_if_I_have_result_but_no_consensus(self):
        self.block_consensus.member_counts[10] = 4
        self.block_consensus.minted_blocks[10] = 'abc'
        self.block_consensus.validation_height = 9

        self.block_consensus.pending_blocks[10] = ['abc', 'abc',  'def', 'def']

        res = self.block_consensus._validate_block(block_num=10, block_hash='abc')

        self.assertFalse(res)

    def test_PRIVATE_METHOD_validate_block__cleans_up_after_validation(self):
        self.block_consensus.member_counts[10] = 2
        self.block_consensus.minted_blocks[10] = 'abc'
        self.block_consensus.validation_height = 9

        self.block_consensus.pending_blocks[10] = ['abc', 'abc', 'abc']

        self.block_consensus._validate_block(block_num=10, block_hash='abc')

        self.assertIsNone(self.block_consensus.minted_blocks.get(10))
        self.assertIsNone(self.block_consensus.pending_blocks.get(10))
        self.assertIsNone(self.block_consensus.member_counts.get(10))

        self.assertEqual(10, self.block_consensus.validation_height)

    def test_METHOD_process_message__adds_new_block_data_to_pending_blocks(self):
        self.block_consensus.member_counts[10] = 10
        msg = {
            'block_num': '10',
            'block_hash': 'abc',
            'vk': 'jeff'
        }

        self.loop.run_until_complete(self.block_consensus.process_message(msg=msg))

        self.assertEqual(['abc'], self.block_consensus.pending_blocks[10])

    def test_METHOD_process_message__does_not_add_new_block_data_if_lower_block_than_valid_height(self):
        self.block_consensus.validation_height = 11
        self.block_consensus.member_counts[10] = 10
        msg = {
            'block_num': '10',
            'block_hash': 'abc',
            'vk': 'jeff'
        }

        self.loop.run_until_complete(self.block_consensus.process_message(msg=msg))

        self.assertEqual(None, self.block_consensus.pending_blocks.get(10))

    def test_METHOD_post_minted_block__adds_new_minted_data_to_minted_blocks(self):
        self.block_consensus.member_counts[10] = 10
        block = {
            'number': '10',
            'hash': 'abc'
        }

        self.block_consensus.post_minted_block(block=block)

        self.assertEqual('abc', self.block_consensus.minted_blocks[10])