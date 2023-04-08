from contracting.db.driver import FSDriver
from lamden import storage
import sys, os

HIGHEST_BLOCK = {"number": "9999999999999999999"}

class AddBlockNumberToState:
    def __init__(self, blocks: storage.BlockStorage=None, driver: FSDriver=None):
        self.blocks = blocks or storage.BlockStorage()
        self.driver = driver or FSDriver()

    def process_blocks(self):
        prev_block = self._get_previous_block(block=HIGHEST_BLOCK)

        while prev_block:
            self._process_block(block=prev_block)
            prev_block = self._get_previous_block(block=prev_block)

    def _process_block(self, block=dict):
        if self.blocks.is_genesis_block(block):
            state_changes = block.get('genesis', [])
        else:
            state_changes = block['processed'].get('state', [])

        rewards = block.get('rewards', [])

        block_num = block.get('number')

        for s in state_changes:
            self.driver.set(s['key'], s['value'], block_num)

        for s in rewards:
            self.driver.set(s['key'], s['value'], block_num)


    def _get_previous_block(self, block=dict):
        block_num = block.get("number")
        return self.blocks.get_previous_block(v=int(block_num))

def main():
    if len(sys.argv) == 1:
        default_path = os.path.join(os.path.expanduser('~'), '.lamden')
        print(f"No argument provided. Defaulting to state directory: {default_path}")
        path = default_path
    else:
        path = sys.argv[1]
        print(f"Using provided state directory: {path}")

    blocks = storage.BlockStorage(root=path)
    driver = FSDriver(root=path)

    repair = AddBlockNumberToState(blocks=blocks, driver=driver)
    repair.process_blocks()

if __name__ == "__main__":
    main()