from lamden.utils.add_block_num_to_state import AddBlockNum
from tests.integration.mock.mock_data_structures import MockBlocks
from lamden.nodes.hlc import HLC_Clock
from lamden.storage import BlockStorage
from contracting.db.driver import FSDriver

import os
import shutil
from unittest import TestCase


class TestMigrateBlocksDir(TestCase):
    def setUp(self):
        self.test_dir = './.lamden'
        self.test_path = os.path.abspath(self.test_dir)
        self.hlc_clock = HLC_Clock()
        self.mock_blocks = None
        self.blockstorage = BlockStorage(root='./.lamden')
        self.state_driver = FSDriver(root='./.lamden')

        self.create_directories()

        self.block_number_adder = AddBlockNum(lamden_root=self.test_path)

        self.proper_block_numbers = {}


    def tearDown(self):
        pass

    def setup_blocks(self):
        self.create_blocks()
        self.store_blocks()

    def create_directories(self):
        if os.path.exists(self.test_path):
            shutil.rmtree(self.test_path)

        os.makedirs(self.test_path)

    def create_blocks(self):
        self.mock_blocks = MockBlocks(
            num_of_blocks=10
        )

        for sc in self.mock_blocks.blocks['0'].get('genesis'):
            self.proper_block_numbers[sc.get('key')] = 0

        for block_number in self.mock_blocks.block_numbers_list:
            if int(block_number) > 0:
                block = self.mock_blocks.blocks[block_number]
                block['number'] = str(int(block_number) + 1)

                state_changes = self.get_state_changes(block=block)

                for sc in state_changes:
                    sc['value'] = sc['value'] + 10
                    self.proper_block_numbers[sc.get('key')] = block.get('number')

                block['processed']['state'] = state_changes

                self.mock_blocks.blocks[block['number']] = block

    def store_blocks(self):
        for block_num in self.mock_blocks.blocks.keys():
            self.blockstorage.store_block(self.mock_blocks.blocks[block_num])

    def get_state_changes(self, block):
        if self.blockstorage.is_genesis_block(block=block):
            return block.get('genesis', [])

        processed = block.get('processed', {})
        state_changes: list = processed.get('state', [])
        rewards: list = processed.get('rewards', [])

        state_changes.extend(rewards)
        return state_changes

    def test_METHOD_start__all_state_has_blocknum(self):
        '''
            1. Create some blocks that have state changes
            2. Apply those state changes without block numbers
            3. Call AddBlockNum
            4. Test that the values are added according to the proper block height (safe_set)
        '''
        self.setup_blocks()

        block_numbers = self.mock_blocks.block_numbers_list

        # Check to see that the state has no block numbers currently
        for block_num in block_numbers:
            block = self.mock_blocks.blocks[block_num]
            state_changes = self.get_state_changes(block=block)

            for sc in state_changes:
                stored_block_num = self.state_driver.get_block(item=sc.get('key'))
                self.assertEqual(-1, stored_block_num)

        # Migrate State by adding block numbers
        self.block_number_adder.start()

        # Check to see that the state now has block numbers and they are correct.
        for block_num in block_numbers:
            block = self.mock_blocks.blocks[block_num]
            state_changes = self.get_state_changes(block=block)

            for sc in state_changes:
                stored_block_num = self.state_driver.get_block(item=sc.get('key'))
                self.assertEqual(int(self.proper_block_numbers.get(sc.get('key'))), int(stored_block_num))




