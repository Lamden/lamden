from unittest import TestCase

from contracting.db.driver import ContractDriver, FSDriver
from contracting.db.encoder import convert_dict, encode, decode

from lamden.nodes.rollback_blocks import RollbackBlocksHandler
from tests.integration.mock.mock_data_structures import MockBlocks
from lamden.nodes.events import Event, EventWriter
from lamden.storage import BlockStorage, NonceStorage
from lamden.crypto.wallet import Wallet

import os
import shutil
import asyncio


class TestRollbackBlocksHandler(TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.test_dir = os.path.abspath('./.lamden')

        self.create_directories()

        self.block_storage = BlockStorage(root=self.test_dir)
        self.state_driver = FSDriver(root=self.test_dir)
        self.contract_driver = ContractDriver(driver=self.state_driver)
        self.nonce_storage = NonceStorage(root=self.test_dir)
        self.event_writer = EventWriter(root=os.path.join(self.test_dir, 'events'))
        self.wallet = Wallet()

        self.rollback_blocks_handler: RollbackBlocksHandler = None

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

    def create_rollback_blocks_handler(self):
        self.rollback_blocks_handler = RollbackBlocksHandler(
            block_storage=self.block_storage,
            nonce_storage=self.nonce_storage,
            contract_driver=self.contract_driver,
            wallet=self.wallet,
            event_writer=self.event_writer
        )

    def test_INSTANCE_init__creates_all_properties(self):
        self.create_rollback_blocks_handler()

        # drivers are not None
        self.assertIsInstance(self.rollback_blocks_handler.block_storage, BlockStorage)
        self.assertIsInstance(self.rollback_blocks_handler.nonce_storage, NonceStorage)
        self.assertIsInstance(self.rollback_blocks_handler.contract_driver, ContractDriver)
        self.assertIsInstance(self.rollback_blocks_handler.wallet, Wallet)
        self.assertIsInstance(self.rollback_blocks_handler.event_writer, EventWriter)

    def test_PRIVATE_METHOD_validate_rollback_point__FALSE_if_None(self):
        self.create_rollback_blocks_handler()

        self.assertFalse(self.rollback_blocks_handler._validate_rollback_point(rollback_point=None))

    def test_PRIVATE_METHOD_validate_rollback_point__FALSE_if_int_ValueError(self):
        self.create_rollback_blocks_handler()

        self.assertFalse(self.rollback_blocks_handler._validate_rollback_point(rollback_point="abc"))

    def test_PRIVATE_METHOD_validate_rollback_point__TRUE_if_string_int(self):
        self.create_rollback_blocks_handler()

        self.assertTrue(self.rollback_blocks_handler._validate_rollback_point(rollback_point="1234"))

    def test_PRIVATE_METHOD_validate_rollback_sets_ref_to_0_if_neg(self):
        self.create_rollback_blocks_handler()

        rollback_point = self.rollback_blocks_handler._validate_rollback_point(rollback_point="-1")

        self.assertEqual("0", rollback_point)

    def test_METHOD_delete_greater_blocks(self):
        self.create_rollback_blocks_handler()

        mock_blocks = MockBlocks(num_of_blocks=10)

        for block in mock_blocks.block_list:
            self.rollback_blocks_handler.block_storage.store_block(block=block)

        rollback_point = mock_blocks.block_list[4]['number']

        self.rollback_blocks_handler.delete_greater_blocks(rollback_point=rollback_point)

        for block in mock_blocks.block_list:
            if block['number'] > rollback_point:
                self.assertIsNone(self.rollback_blocks_handler.block_storage.get_block(block['number']))
            else:
                self.assertIsNotNone(self.rollback_blocks_handler.block_storage.get_block(block['number']))

        self.assertEqual(5, self.block_storage.block_driver.total_files)

    def test_METHOD_purge_current_state(self):
        self.create_rollback_blocks_handler()

        mock_blocks = MockBlocks(num_of_blocks=10)

        for block in mock_blocks.block_list:
            self.rollback_blocks_handler.block_storage.store_block(block=block)
            self.rollback_blocks_handler._safe_set_state_changes_and_rewards(block=block)
            self.rollback_blocks_handler._save_nonce_information(block=block)

        # Validate state exists before purge
        for block in mock_blocks.block_list:
            if self.block_storage.is_genesis_block(block):
                state_changes = block['genesis']
                sender = None
            else:
                state_changes = block['processed'].get('state', [])
                sender = block['processed']['transaction']['payload']['sender']
                processor = block['processed']['transaction']['payload']['processor']

                for state_change in state_changes:
                    block_state_change_key = state_change.get('key')

                    block_state_change_value = state_change.get('value')
                    block_state_change_value_decoded = decode(encode(block_state_change_value))

                    state_value = self.contract_driver.get(key=block_state_change_key)
                    self.assertEqual(block_state_change_value_decoded, state_value)

                if sender is not None:
                    nonce = self.nonce_storage.get_nonce(sender=sender, processor=processor)
                    self.assertIsNotNone(nonce)



        # purge state
        self.rollback_blocks_handler.purge_current_state()

        # Validate state does not exist after purge
        for block in mock_blocks.block_list:
            if self.block_storage.is_genesis_block(block):
                state_changes = block['genesis']
                sender = None
            else:
                state_changes = block['processed'].get('state', [])
                sender = block['processed']['transaction']['payload']['sender']
                processor = block['processed']['transaction']['payload']['processor']

                for state_change in state_changes:
                    block_state_change_key = state_change.get('key')

                    state_value = self.contract_driver.get(key=block_state_change_key)
                    self.assertIsNone(state_value)

                if sender is not None:
                    nonce = self.nonce_storage.get_nonce(sender=sender, processor=processor)
                    self.assertIsNone(nonce)

    def test_METHOD_process_genesis_block__saves_genesis_block_state(self):
        self.create_rollback_blocks_handler()

        mock_blocks = MockBlocks(num_of_blocks=10)

        for block in mock_blocks.block_list:
            self.rollback_blocks_handler.block_storage.store_block(block=block)

        genesis_block = mock_blocks.block_list[0]

        # Save genesis state
        self.rollback_blocks_handler.process_genesis_block()

        for state_change in genesis_block.get('genesis'):
            block_state_change_key = state_change.get('key')

            block_state_change_value = state_change.get('value')
            block_state_change_value_decoded = decode(encode(block_state_change_value))

            state_value = self.contract_driver.get(key=block_state_change_key)
            self.assertEqual(block_state_change_value_decoded, state_value)

    def test_METHOD_process_all_blocks__saves_block_data_stops_at_genesis_block(self):
        self.create_rollback_blocks_handler()

        mock_blocks = MockBlocks(num_of_blocks=10)

        for block in mock_blocks.block_list:
            self.rollback_blocks_handler.block_storage.store_block(block=block)

        # Save state and rewards from all blocks
        self.rollback_blocks_handler.process_all_blocks()

        # Validate state does not exist after purge
        for block in mock_blocks.block_list:
            if self.block_storage.is_genesis_block(block):
                break
            else:
                state_changes = block['processed'].get('state', [])
                sender = block['processed']['transaction']['payload']['sender']
                processor = block['processed']['transaction']['payload']['processor']

                for state_change in state_changes:
                    block_state_change_key = state_change.get('key')

                    state_value = self.contract_driver.get(key=block_state_change_key)
                    self.assertIsNone(state_value)

                if sender is not None:
                    nonce = self.nonce_storage.get_nonce(sender=sender, processor=processor)
                    self.assertIsNone(nonce)


    def test_METHOD_run__rollsback_blocks_and_state(self):
        self.create_rollback_blocks_handler()

        mock_blocks = MockBlocks(num_of_blocks=10)

        for block in mock_blocks.block_list:
            self.rollback_blocks_handler.block_storage.store_block(block=block)
            self.rollback_blocks_handler._safe_set_state_changes_and_rewards(block=block)
            self.rollback_blocks_handler._save_nonce_information(block=block)

        # Validate ALL state exists before rollback
        for block in mock_blocks.block_list:
            if self.block_storage.is_genesis_block(block):
                state_changes = block['genesis']
                sender = None
            else:
                state_changes = block['processed'].get('state', [])
                sender = block['processed']['transaction']['payload']['sender']
                processor = block['processed']['transaction']['payload']['processor']

                for state_change in state_changes:
                    block_state_change_key = state_change.get('key')

                    block_state_change_value = state_change.get('value')
                    block_state_change_value_decoded = decode(encode(block_state_change_value))

                    state_value = self.contract_driver.get(key=block_state_change_key)
                    self.assertEqual(block_state_change_value_decoded, state_value)

                if sender is not None:
                    block_nonce = block['processed']['transaction']['payload']['nonce']
                    nonce = self.nonce_storage.get_nonce(sender=sender, processor=processor)
                    self.assertGreaterEqual(block_nonce, nonce)


        rollback_point = mock_blocks.block_list[3].get('number')

        # ROLLBACK
        tasks = asyncio.gather(
            self.rollback_blocks_handler.run(rollback_point=rollback_point)
        )
        self.loop.run_until_complete(tasks)


        # Validate state after rollback
        for block in mock_blocks.block_list:
            if self.block_storage.is_genesis_block(block):
                state_changes = block['genesis']
                sender = None
            else:
                state_changes = block['processed'].get('state', [])
                sender = block['processed']['transaction']['payload']['sender']
                processor = block['processed']['transaction']['payload']['processor']

                for state_change in state_changes:
                    block_state_change_key = state_change.get('key')

                    block_state_change_value = state_change.get('value')
                    block_state_change_value_decoded = decode(encode(block_state_change_value))

                    state_value = self.contract_driver.get(key=block_state_change_key)

                    if int(block.get('number')) > int(rollback_point):
                        self.assertIsNone(state_value)
                    else:
                        self.assertEqual(block_state_change_value_decoded, state_value)

                if sender is not None:
                    block_nonce = block['processed']['transaction']['payload']['nonce']
                    nonce = self.nonce_storage.get_nonce(sender=sender, processor=processor)

                    # nonce will be less than block nonce if the block is after the rollback point
                    if block.get('number') > rollback_point:
                        self.assertLessEqual(block_nonce, nonce)
                    else:
                        # block should be greater of equal because the nonce was saved
                        self.assertGreaterEqual(block_nonce, nonce)