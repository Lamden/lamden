from unittest import TestCase
from tests.integration.mock.mock_data_structures import MockBlocks, MockTransaction

from lamden.storage import BlockStorage
from lamden.crypto.wallet import Wallet
from lamden.crypto.canonical import hash_members_list

from lamden.nodes.validate_chain import ValidateChainHandler


import os
import shutil
import json
import asyncio


class TestMemberHistoryHandler(TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.test_dir = os.path.abspath('./.lamden')

        self.create_directories()

        self.block_storage = BlockStorage(root=self.test_dir)
        self.mock_blocks: MockBlocks = None

        self.validate_chain_handler: ValidateChainHandler = None

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

    def create_handler(self):
        self.validate_chain_handler = ValidateChainHandler(
            block_storage=self.block_storage
        )

    def add_blocks_to_storage(self, amount: int = 0):
        if self.mock_blocks is None:
            self.mock_blocks = MockBlocks(num_of_blocks=amount)

        for block in self.mock_blocks.block_list:
            self.block_storage.store_block(block=block)

    def add_member_list_change(self, member_wallets: list):
        new_block = self.mock_blocks.add_block(member_wallets=member_wallets)
        self.block_storage.store_block(block=new_block)


    def test_INSTANCE__can_create_instance(self):
        validate_chain_handler = ValidateChainHandler(
            block_storage=self.block_storage
        )

        self.assertIsInstance(validate_chain_handler, ValidateChainHandler)

    def test_METHOD_save_member_history__can_save_member_history_from_block(self):
        self.create_handler()

        members_list = [Wallet().verifying_key, Wallet().verifying_key, Wallet().verifying_key]
        block = {
            'number': '1234',
            'processed': {
                'state': [
                    {
                        'key': 'masternodes.S:members',
                        'value': members_list
                    }
                ]
            }
        }

        self.validate_chain_handler.save_member_history(block=block)

        self.assertEqual(members_list, self.block_storage.member_history.get(block_num='1235'))

        for member in members_list:
            self.assertTrue(self.block_storage.is_member_at_block_height(block_num='1235', vk=member))

    def test_METHOD_save_member_history__can_save_member_history_from_GENESIS_block(self):
        self.create_handler()

        members_list = [Wallet().verifying_key, Wallet().verifying_key, Wallet().verifying_key]
        block = {
            'number': '0',
            'genesis': [
                    {
                        'key': 'masternodes.S:members',
                        'value': members_list
                    }
                ]
        }

        self.validate_chain_handler.save_member_history(block=block)

        self.assertEqual(members_list, self.block_storage.member_history.get(block_num='1'))

        for member in members_list:
            self.assertTrue(self.block_storage.is_member_at_block_height(block_num='1', vk=member))

    def test_METHOD_process_genesis_block__validates_block_and_saves_members(self):
        self.create_handler()
        self.add_blocks_to_storage(amount=10)

        self.validate_chain_handler.process_genesis_block()

        members_list = self.mock_blocks.initial_members.get('masternodes')

        self.assertEqual(members_list, self.block_storage.member_history.get(block_num='1'))

        for member in members_list:
            self.assertTrue(self.block_storage.is_member_at_block_height(block_num='1', vk=member))

    def test_METHOD_process_genesis_block__validates_block_and_saves_members(self):
        self.create_handler()

        self.mock_blocks = MockBlocks(num_of_blocks=10)
        self.mock_blocks.blocks['0']['hash'] = 'abc'

        self.add_blocks_to_storage()

        self.add_blocks_to_storage(amount=10)

        with self.assertRaises(AssertionError):
            self.validate_chain_handler.process_genesis_block()


    def test_METHOD_validate_block__validates_block_raises_no_exceptions(self):
        self.create_handler()
        self.add_blocks_to_storage(amount=10)

        block = self.mock_blocks.block_list[1]

        try:
            self.validate_chain_handler.validate_block(block=block)
        except Exception:
            self.fail("This should raise NO exceptions unless the block is invalid.")

    def test_METHOD_validate_block__raises_AssertionError_if_block_invalid(self):
        self.create_handler()

        self.mock_blocks = MockBlocks(num_of_blocks=10)
        block = self.mock_blocks.block_list[-1]
        block['hash'] = 'abc'

        with self.assertRaises(AssertionError):
            self.validate_chain_handler.validate_block(block=block)

    def test_METHOD_process_all_blocks__raises_no_exceptions_if_all_valid(self):
        self.create_handler()
        self.mock_blocks = MockBlocks(num_of_blocks=100)
        self.add_blocks_to_storage()
        self.validate_chain_handler.process_genesis_block()

        new_members_wallets = [Wallet(), Wallet(), Wallet()]
        new_members_list = [wallet.verifying_key for wallet in new_members_wallets]

        # Validate the new members aren't currently members
        last_block_number = self.mock_blocks.block_list[-1].get('number')
        for member in new_members_list:
            self.assertFalse(self.block_storage.is_member_at_block_height(block_num=int(last_block_number) + 1, vk=member))

        self.add_member_list_change(member_wallets=new_members_wallets)

        try:
            self.validate_chain_handler.process_all_blocks()
        except Exception:
            self.fail("This should raise NO exceptions unless the block is invalid.")

        # Test that the member change was picked up off the last block
        last_block_number = self.mock_blocks.block_list[-1].get('number')
        for member in new_members_list:
            self.assertTrue(self.block_storage.is_member_at_block_height(block_num=int(last_block_number) + 1, vk=member))

    def test_METHOD_validate_consensus__should_raise_no_errors_if_all_members_valid(self):
        self.create_handler()
        self.mock_blocks = MockBlocks(num_of_blocks=10)

        new_members_wallets = [Wallet(), Wallet(), Wallet()]
        new_members_list = [wallet.verifying_key for wallet in new_members_wallets]

        member_change_block = self.mock_blocks.add_block(member_wallets=new_members_wallets)
        member_change_block_number = member_change_block.get('number')
        self.block_storage.member_history.set(block_num=member_change_block_number, members_list=new_members_list)

        last_block = self.mock_blocks.add_block()

        try:
            self.validate_chain_handler.validate_consensus(block=last_block)
        except Exception:
            self.fail("This should raise NO exceptions unless proof signers are not in members list.")

    def test_METHOD_validate_consensus__raises_AssertionError_if_proof_signer_not_member(self):
        self.create_handler()
        self.mock_blocks = MockBlocks(num_of_blocks=10)

        new_members_wallets = [Wallet(), Wallet(), Wallet()]
        new_members_list = [wallet.verifying_key for wallet in new_members_wallets]

        member_change_block = self.mock_blocks.add_block(member_wallets=new_members_wallets)
        member_change_block_number = member_change_block.get('number')
        self.block_storage.member_history.set(block_num=member_change_block_number, members_list=new_members_list)

        last_block = self.mock_blocks.add_block()
        last_block['proofs'].append({
            'signer': Wallet().verifying_key
        })

        with self.assertRaises(AssertionError):
            self.validate_chain_handler.validate_consensus(block=last_block)
