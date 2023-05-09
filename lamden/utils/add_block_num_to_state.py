import os
import sys

from contracting.db.driver import FSDriver
from lamden.storage import BlockStorage, STORAGE_HOME

class AddBlockNum:
    def __init__(self, lamden_root = None):

        if lamden_root is None:
            lamden_root = STORAGE_HOME

        self.lamden_root = os.path.abspath(lamden_root)

        self.state_driver = FSDriver(root=self.lamden_root)
        self.block_storage = BlockStorage(root=self.lamden_root)

    def start(self):
        '''
            1. read in all blocks from first to last
            2. call safe_set on all blocks to set theeblock number in the state
        '''

        max_block_num = int("99999999999999999999")
        prev_block = self.block_storage.get_previous_block(v=max_block_num)

        while True:
            if prev_block is None:
                break

            block_num = prev_block.get('number')

            if block_num == '0':
                break

            if self.block_storage.is_genesis_block(block=prev_block):
                state_changes = prev_block.get('genesis', [])
            else:
                processed = prev_block.get('processed', {})
                state_changes = processed.get('state', [])

            # Apply state changes with block number
            for stage_change in state_changes:
                self.state_driver.set(stage_change.get('key'), stage_change.get('value'), block_num=block_num)

            rewards = prev_block.get('rewards', [])
            for stage_change in rewards:
                self.state_driver.set(stage_change.get('key'), stage_change.get('value'), block_num=block_num)

            prev_block = self.block_storage.get_previous_block(v=int(block_num))



if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python migrate_blocks_dir.py <lamden_root_directory>")
        sys.exit(1)

    lamden_root = sys.argv[1]

    block_num_adder = AddBlockNum(lamden_root=lamden_root)
    block_num_adder.start()

    print("Task Completed.")
