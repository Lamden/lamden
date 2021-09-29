from unittest import TestCase
from lamden import storage

from tests.unit.helpers.mock_blocks import generate_blocks
from lamden.nodes.hlc import HLC_Clock

import time

class TestStorage(TestCase):
    def setUp(self):
        self.blocks = storage.BlockStorage(home="./.lamden")

        self.hlc_clock = HLC_Clock()

    def tearDown(self):
        self.blocks.flush()

    def test_store_block(self):
        prev_block_hlc = self.hlc_clock.get_new_hlc_timestamp()

        blocks = generate_blocks(
            number_of_blocks=1,
            starting_block_num=0,
            prev_block_hash='0' * 64,
            prev_block_hlc=prev_block_hlc
        )

        self.blocks.store_block(blocks[0])

        self.assertIsNotNone(self.blocks.get_block(1))

    def test_get_block(self):
        prev_block_hlc = self.hlc_clock.get_new_hlc_timestamp()

        blocks = generate_blocks(
            number_of_blocks=3,
            starting_block_num=0,
            prev_block_hash='0' * 64,
            prev_block_hlc=prev_block_hlc
        )

        for block in blocks:
            self.blocks.store_block(block)

        block_2 = self.blocks.get_block(2)

        self.assertEqual(2, block_2.get('number'))

    def test_get_block(self):
        prev_block_hlc = self.hlc_clock.get_new_hlc_timestamp()

        blocks = generate_blocks(
            number_of_blocks=3,
            starting_block_num=0,
            prev_block_hash='0' * 64,
            prev_block_hlc=prev_block_hlc
        )

        for block in blocks:
            self.blocks.store_block(block)

        block_2 = self.blocks.get_block(2)

        self.assertEqual(2, block_2.get('number'))

    def test_get_later_blocks(self):
        blocks_1 = generate_blocks(
            number_of_blocks=3,
            starting_block_num=0,
            prev_block_hash='0' * 64,
            prev_block_hlc=self.hlc_clock.get_new_hlc_timestamp()
        )

        for block in blocks_1:
            self.blocks.store_block(block)

        consensus_hlc = self.hlc_clock.get_new_hlc_timestamp()
        time.sleep(0.1)

        blocks_2 = generate_blocks(
            number_of_blocks=3,
            starting_block_num=blocks_1[2].get('number'),
            prev_block_hash=blocks_1[2].get('previous'),
            prev_block_hlc=self.hlc_clock.get_new_hlc_timestamp()
        )

        for block in blocks_2:
            self.blocks.store_block(block)

        later_blocks = self.blocks.get_later_blocks(6, consensus_hlc)

        self.assertEqual(3, len(later_blocks))
        self.assertEqual(6, later_blocks[2].get('number'))





