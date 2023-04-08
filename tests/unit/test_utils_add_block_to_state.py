from lamden.utils.add_block_number import AddBlockNumberToState
from lamden.storage import BlockStorage
from lamden.crypto.wallet import Wallet
from tests.unit.helpers.mock_blocks import generate_blocks, GENESIS_BLOCK
from contracting.db.driver import FSDriver
import os, copy, shutil
from pathlib import Path
from unittest import TestCase
import random



class TestAddBlockNumberToState(TestCase):
    def setUp(self):

        self.create_lamden_directory()
        self.driver = FSDriver(root=Path('./.lamden'))
        self.blocks = BlockStorage(root=Path('./.lamden'))

        self.masternodes = [Wallet() for i in range(3)]
        self.wallets = [Wallet() for i in range(10)]
        self.testing_state = {}
        self.setup_blocks()

        self.add_block_number = AddBlockNumberToState(
            blocks=self.blocks,
            driver=self.driver
        )

    def tearDown(self):
        pass

    def create_lamden_directory(self):
        if os.path.exists(Path('./.lamden')):
            shutil.rmtree(Path('./.lamden'))

        os.makedirs(Path('./.lamden'))

    def setup_blocks(self):
        GENESIS_BLOCK['hlc_timestamp'] = "2023-03-30T18:09:58.399507456Z_0"
        self.blocks.store_block(GENESIS_BLOCK)

        blocks = generate_blocks(
            number_of_blocks=20,
            prev_block_hlc=GENESIS_BLOCK.get('hlc_timestamp'),
            prev_block_hash=GENESIS_BLOCK.get('hash')
        )

        for block in blocks:
            block['number'] = str(block['number'])
            self.add_state_to_block(block)
            self.blocks.store_block(copy.deepcopy(block))
            self.set_state(block)

    def add_state_to_block(self, block):
        state = [self.create_state_entry(random.choice(self.wallets)) for i in range(random.randint(3, 8))]
        block['processed']['state'] = state
        block['rewards'] = [self.create_state_entry(masternode) for masternode in self.masternodes]

    def create_state_entry(self, wallet: Wallet):
        return {
            "key": f'currency.balances:{wallet.verifying_key}',
            "value": {
                "__fixed__": f'{random.randint(1000, 50000)}.{random.randint(1000, 50000)}'
            }
        }

    def set_state(self, block):
        if self.blocks.is_genesis_block(block):
            state_changes = block.get('genesis', [])
        else:
            state_changes = block['processed'].get('state', [])

        rewards = block.get('rewards', [])
        block_num = block.get('number')

        for s in state_changes:
            key = s['key']
            value = s['value']
            self.store_value_in_testing_state(key, value, block_num)
            self.driver.set(key, value)

        for s in rewards:
            key = s['key']
            value = s['value']
            self.store_value_in_testing_state(key, value, block_num)
            self.driver.set(key, value)

    def store_value_in_testing_state(self, key, value, block_num):
        current_state = self.testing_state.get(key, {})
        current_block = current_state.get('block_num', "-1")

        if int(block_num) >= int(current_block):
            self.testing_state[key] = {
                'block_num': block_num,
                'value': value
            }

    def test__process_blocks(self):
        self.add_block_number.process_blocks()

        for k, testing_value in [(key, self.testing_state[key]['value']['__fixed__']) for key in self.testing_state.keys()]:
            driver_value = str(self.driver.get(k))

            self.assertEqual(testing_value, driver_value)
