from unittest import TestCase
from lamden.storage import BlockStorage, NonceStorage, LATEST_BLOCK_HASH_KEY, LATEST_BLOCK_HEIGHT_KEY
from lamden.crypto.wallet import Wallet
from contracting.db.driver import ContractDriver, FSDriver
from lamden.nodes.missing_blocks import MissingBlocksHandler, MissingBlocksWriter
from tests.integration.mock.mock_data_structures import MockBlocks
from contracting.db.encoder import encode
from lamden.nodes.events import Event, EventWriter

import hashlib

import os
import shutil
import json
import asyncio
from copy import deepcopy

# MOCK NETWORK
class Network:
    def __init__(self):
        self.peers = []

    def get_all_connected_peers(self):
        return self.peers

    def add_peer(self, blocks={}):
        self.peers.append(MockPeer(blocks=blocks))

    def get_peer(self, vk: str):
        for peer in self.peers:
            if peer.server_vk == vk:
                return peer

class MockPeer:
    def __init__(self, blocks={}):
        self.blocks = blocks

        wallet = Wallet()
        self.server_vk = wallet.verifying_key

    def find_block(self, block_num: str) -> dict:
        return self.blocks.get(block_num, None)

    async def get_block(self, block_num: int) -> (dict, None):
        block = self.find_block(str(block_num))
        block = json.loads(encode(block))
        if block is None:
            return  {'block_info': None}

        return {'block_info': block}


class TestMissingBlocksHandler(TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.test_dir = os.path.abspath('./.lamden')
        self.missing_blocks_dir = os.path.join(self.test_dir, "missing_blocks")
        self.missing_blocks_filename = "missing_blocks.json"

        self.full_filename_path = os.path.join(self.missing_blocks_dir, self.missing_blocks_filename)

        self.create_directories()

        self.block_storage = BlockStorage(root=self.test_dir)
        self.state_driver = FSDriver(root=self.test_dir)
        self.contract_driver = ContractDriver(driver=self.state_driver)
        self.nonce_storage = NonceStorage(root=self.test_dir)
        self.mock_network = Network()
        self.event_writer = EventWriter(root=os.path.join(self.test_dir, 'events'))
        self.wallet = Wallet()

        self.missing_blocks_handler: MissingBlocksHandler = None

    def tearDown(self):
        try:
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.close()
        except RuntimeError:
            pass

    def create_missing_blocks_handler(self):
        self.missing_blocks_handler = MissingBlocksHandler(
            block_storage=self.block_storage,
            nonce_storage=self.nonce_storage,
            contract_driver=self.contract_driver,
            network=self.mock_network,
            wallet=self.wallet,
            event_writer=self.event_writer,
            root=self.test_dir
        )

    def create_directories(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

        os.makedirs(self.test_dir)

    def add_peers_to_network(self, amount, blocks={}):
        blocks = dict(blocks)
        for i in range(amount):
            self.mock_network.add_peer(blocks=blocks)

    def test_INSTANCE_init__creates_all_properties(self):
        # if the missing blocks directory exists, remove it so we can test it gets created
        if os.path.exists(self.missing_blocks_dir):
            shutil.rmtree(self.missing_blocks_dir)

        self.create_missing_blocks_handler()

        # drivers are not None
        self.assertIsInstance(self.missing_blocks_handler.block_storage, BlockStorage)
        self.assertIsInstance(self.missing_blocks_handler.nonce_storage, NonceStorage)
        self.assertIsInstance(self.missing_blocks_handler.contract_driver, ContractDriver)
        self.assertIsInstance(self.missing_blocks_handler.network, Network)
        self.assertIsInstance(self.missing_blocks_handler.wallet, Wallet)

        # root dir is stored as passed
        self.assertEqual(self.test_dir, self.missing_blocks_handler.root)

        # missing blocks directory is defined as a child of root
        self.assertEqual(self.missing_blocks_dir, self.missing_blocks_handler.missing_blocks_dir)

    def test_INSTANCE_init__creates_directory_if_it_does_not_exist(self):
        # if the missing blocks directory exists, remove it so we can test it gets created
        if os.path.exists(self.missing_blocks_dir):
            shutil.rmtree(self.missing_blocks_dir)

        self.create_missing_blocks_handler()

        self.assertTrue(os.path.exists(self.test_dir))

    def test_INSTANCE_init__does_not_error_if_directory_already_exists(self):
        # if the missing blocks directory exists, remove it so we can test it gets created
        if os.path.exists(self.missing_blocks_dir):
            shutil.rmtree(self.missing_blocks_dir)

        os.makedirs(self.missing_blocks_dir)

        # Assert dir exists
        self.assertTrue(os.path.exists(self.test_dir))

        # Should not fail
        try:
            self.create_missing_blocks_handler()
        except FileExistsError:
            self.fail("This should not create an exception.")


    def test_PRIVATE_METHOD_read_missing_blocks_file__returns_json_decoded_data_is_list(self):
        self.create_missing_blocks_handler()

        data = ["1682939321560636160", "8520679865965181957", "2156250479259241801"]

        # Open a file for writing
        with open(self.full_filename_path, "w") as outfile:
            # Write the Python dictionary as a JSON string to the file
            json.dump(data, outfile)

        missing_blocks = self.missing_blocks_handler._read_missing_blocks_file()
        self.assertIsNotNone(missing_blocks)
        self.assertIsInstance(missing_blocks, list)
        self.assertEqual(3, len(missing_blocks))

    def test_PRIVATE_METHOD_read_missing_blocks_file__returns_None_if_not_exists(self):
        self.create_missing_blocks_handler()

        self.assertFalse(os.path.exists(self.full_filename_path))
        missing_blocks = self.missing_blocks_handler._read_missing_blocks_file()

        self.assertIsNone(missing_blocks)

    def test_PRIVATE_METHOD_read_missing_blocks_file__returns_None_if_not_json(self):
        self.create_missing_blocks_handler()

        data = "1682939321560636160, 8520679865965181957, 2156250479259241801"

        # Open a file for writing
        with open(self.full_filename_path, "w") as outfile:
            # Write the Python dictionary as a JSON string to the file
            outfile.write(data)

        self.assertTrue(os.path.exists(self.full_filename_path))

        missing_blocks = self.missing_blocks_handler._read_missing_blocks_file()

        self.assertIsNone(missing_blocks)

    def test_PRIVATE_METHOD_validate_missing_blocks_data__returns_FALSE_if_data_None(self):
        self.create_missing_blocks_handler()

        is_valid = self.missing_blocks_handler._validate_missing_blocks_data(data=None)

        self.assertFalse(is_valid)

    def test_PRIVATE_METHOD_validate_missing_blocks_data__returns_FALSE_if_data_not_list(self):
        self.create_missing_blocks_handler()

        is_valid = self.missing_blocks_handler._validate_missing_blocks_data(data={})

        self.assertFalse(is_valid)

    def test_PRIVATE_METHOD_validate_missing_blocks_data__returns_FALSE_if_data_is_list_not_string(self):
        self.create_missing_blocks_handler()

        is_valid = self.missing_blocks_handler._validate_missing_blocks_data(
            data=[
                1682939321560636160,
                "8520679865965181957",
                2156250479259241801
            ])

        self.assertFalse(is_valid)

    def test_PRIVATE_METHOD_validate_missing_blocks_data__returns_TRUE_if_data_is_list_of_strings(self):
        self.create_missing_blocks_handler()

        is_valid = self.missing_blocks_handler._validate_missing_blocks_data(
            data=[
                "1682939321560636160",
                "8520679865965181957",
                "2156250479259241801"
            ])

        self.assertTrue(is_valid)

    def test_PRIVATE_METHOD_delete_missing_blocks_file__deletes_file_if_exists(self):
        self.create_missing_blocks_handler()

        data = ["1682939321560636160", "8520679865965181957", "2156250479259241801"]

        # Open a file for writing
        with open(self.full_filename_path, "w") as outfile:
            # Write the Python dictionary as a JSON string to the file
            json.dump(data, outfile)

        # assert the file does exist
        self.assertTrue(os.path.exists(self.full_filename_path))

        self.missing_blocks_handler._delete_missing_blocks_file()

        # assert the file was deleted
        self.assertFalse(os.path.exists(self.full_filename_path))

    def test_PRIVATE_METHOD_delete_missing_blocks_file__does_not_error_if_file_not_exist(self):
        self.create_missing_blocks_handler()

        # assert the file does NOT exist
        self.assertFalse(os.path.exists(self.full_filename_path))

        try:
            self.missing_blocks_handler._delete_missing_blocks_file()
        except FileNotFoundError:
            self.fail("This should not create an exception.")

    def test_METHOD_get_missing_blocks_list__gets_empty_list_if_no_file(self):
        self.create_missing_blocks_handler()

        missing_blocks = self.missing_blocks_handler.get_missing_blocks_list()

        self.assertIsInstance(missing_blocks, list)
        self.assertEqual(0, len(missing_blocks))

    def test_METHOD_get_missing_blocks_list__returns_file_content_and_removes_file(self):
        self.create_missing_blocks_handler()

        data = ["1682939321560636160", "8520679865965181957", "2156250479259241801"]

        # Open a file for writing
        with open(self.full_filename_path, "w") as outfile:
            # Write the Python dictionary as a JSON string to the file
            json.dump(data, outfile)

        missing_blocks = self.missing_blocks_handler.get_missing_blocks_list()

        # returned list of blocks
        self.assertIsInstance(missing_blocks, list)
        self.assertEqual(3, len(missing_blocks))

        # deleted file afterwards
        self.assertFalse(os.path.exists(self.full_filename_path))

    def test_METHOD_process_block__returns_if_block_already_exists(self):
        self.create_missing_blocks_handler()

        mock_blocks = MockBlocks(num_of_blocks=2)

        for block in mock_blocks.block_list:
            self.missing_blocks_handler.block_storage.store_block(block=block)

        result = self.missing_blocks_handler.process_block(block=mock_blocks.latest_block)

        self.assertEqual('already_exists', result)

    def test_METHOD_process_block__processes_block_state_and_nonce_and_saved_in_storage(self):
        expected_jeff_bal = '456'
        expected_stu_bal = '789'
        expected_testing_val = True
        expected_nonce = 100
        block_number = '1682939321560636160'
        block_hash = 'fcf68695ed53d23939d5f82198cc61d7fbf20837f69c16b963f1dc9e0162a5c2'
        tx_hash = 'ffe2f8ef7664c12804739a5a4b8ede34aa61a99111eae760c5a114e26774711c'

        block = {
            'number': block_number,
            'hash': block_hash,
            'processed': {
                'hash': tx_hash,
                'transaction': {
                    'payload':{
                        'nonce': expected_nonce,
                        'processor': 'jeff',
                        'sender': 'stu'
                    }
                },
                'state': [
                    {'key': 'currency.balances:jeff', 'value': {'__fixed__': '123'}},
                    {'key': 'missedblock.testing', 'value': expected_testing_val},
                ]
            },
            'rewards': [
                {'key': 'currency.balances:jeff', 'value': {'__fixed__': expected_jeff_bal}},
                {'key': 'currency.balances:stu', 'value': {'__fixed__': expected_stu_bal}}
            ]
        }

        self.create_missing_blocks_handler()

        self.missing_blocks_handler.process_block(block=block)

        # Saved State
        jeff_bal = self.contract_driver.driver.get('currency.balances:jeff')
        stu_bal = self.contract_driver.driver.get('currency.balances:stu')
        testing_val = self.contract_driver.driver.get('missedblock.testing')

        self.assertEqual(expected_jeff_bal, str(jeff_bal))
        self.assertEqual(expected_stu_bal, str(stu_bal))
        self.assertEqual(expected_testing_val, testing_val)

        # Saved Nonce
        nonce = self.nonce_storage.get_nonce('stu', 'jeff')
        self.assertEqual(expected_nonce, nonce)

        # Saved Block
        saved_block = self.block_storage.get_block(v=int(block_number))

        self.assertIsNotNone(saved_block)
        self.assertDictEqual(block, saved_block)

    def test_PRIVATE_METHOD_source_block_from_peers__can_get_block_from_peer(self):
        mock_blocks = MockBlocks(num_of_blocks=5)
        latest_block_number = mock_blocks.latest_block_number

        self.add_peers_to_network(amount=5, blocks=mock_blocks.blocks)

        self.create_missing_blocks_handler()

        tasks = asyncio.gather(
            self.missing_blocks_handler._source_block_from_peers(block_num=int(latest_block_number))
        )
        res = self.loop.run_until_complete(tasks)

        block = res[0]

        self.assertIsNotNone(block)
        self.assertEqual(latest_block_number, block.get('number'))

    def test_PRIVATE_METHOD_source_block_from_peers__returns_None_if_no_peer_has_block(self):
        mock_blocks = MockBlocks(num_of_blocks=5)
        missing_block_number = "8520679865965181957"

        self.add_peers_to_network(amount=5, blocks=mock_blocks.blocks)

        self.create_missing_blocks_handler()

        tasks = asyncio.gather(
            self.missing_blocks_handler._source_block_from_peers(block_num=int(missing_block_number))
        )
        res = self.loop.run_until_complete(tasks)

        block = res[0]

        self.assertIsNone(block)


    def test_PRIVATE_METHOD_source_block_from_peers__raises_ValueError_on_genesis_block(self):
        self.create_missing_blocks_handler()
        with self.assertRaises(ValueError):
            tasks = asyncio.gather(
                self.missing_blocks_handler._source_block_from_peers(block_num=int(0))
            )
            self.loop.run_until_complete(tasks)

    def test_PRIVATE_METHOD_safe_set_state_changes_and_rewards__sets_state_changes_and_reward_from_block(self):
        self.create_missing_blocks_handler()

        expected_jeff_bal = '456'
        expected_stu_bal = '789'
        expected_testing_val = True

        block_number = '1682939321560636160'

        block = {
            'number': block_number,
            'processed': {
                'state': [
                    {'key': 'currency.balances:jeff', 'value': {'__fixed__': '123'}},
                    {'key': 'missedblock.testing', 'value': expected_testing_val},
                ]
            },
            'rewards': [
                {'key': 'currency.balances:jeff', 'value': {'__fixed__': expected_jeff_bal}},
                {'key': 'currency.balances:stu', 'value': {'__fixed__': expected_stu_bal}}
            ]
        }

        self.missing_blocks_handler._safe_set_state_changes_and_rewards(block=block)

        jeff_bal = self.contract_driver.driver.get('currency.balances:jeff')
        jeff_bal_block = self.contract_driver.driver.get_block('currency.balances:jeff')
        stu_bal = self.contract_driver.driver.get('currency.balances:stu')
        stu_bal_block = self.contract_driver.driver.get_block('currency.balances:stu')
        testing_val = self.contract_driver.driver.get('missedblock.testing')
        testing_val_block = self.contract_driver.driver.get_block('missedblock.testing')

        self.assertEqual(expected_jeff_bal, str(jeff_bal))
        self.assertEqual(block_number, str(jeff_bal_block))
        self.assertEqual(expected_stu_bal, str(stu_bal))
        self.assertEqual(block_number, str(stu_bal_block))
        self.assertEqual(expected_testing_val, testing_val)
        self.assertEqual(block_number, str(testing_val_block))

    def test_PRIVATE_METHOD_save_nonce_information__saves_nonce_from_block(self):
        self.create_missing_blocks_handler()

        expected_nonce = 100
        sender = 'stu'
        processor = 'jeff'
        block = {
            'processed': {
                'transaction': {
                    'payload':{
                        'nonce': expected_nonce,
                        'processor': processor,
                        'sender': sender
                    }
                }
            }
        }

        self.missing_blocks_handler._save_nonce_information(block=block)

        nonce = self.nonce_storage.get_nonce(sender=sender, processor=processor)

        self.assertEqual(expected_nonce, nonce)

    def test_METHOD_process_missing_blocks__processes_a_list_of_block_numbers(self):
        self.create_missing_blocks_handler()

        mock_blocks = MockBlocks(num_of_blocks=5)
        self.add_peers_to_network(amount=5, blocks=mock_blocks.blocks)

        missing_block_numbers_list = [block_num for block_num in mock_blocks.block_numbers_list if int(block_num) != 0]

        tasks = asyncio.gather(
            self.missing_blocks_handler.process_missing_blocks(missing_block_numbers_list=missing_block_numbers_list)
        )
        self.loop.run_until_complete(tasks)

        for block_number in missing_block_numbers_list:
            block = self.missing_blocks_handler.block_storage.get_block(v=int(block_number))
            self.assertIsNotNone(block)

    def test_METHOD_recalc_block_hashes__fixes_hashes_in_future_blocks(self):
        mock_blocks = MockBlocks(num_of_blocks=5)
        self.wallet = mock_blocks.masternode_wallet

        self.create_missing_blocks_handler()


        block_list = [deepcopy(block) for block in mock_blocks.block_list if int(block.get('number')) != 0]
        proper_block_list = [deepcopy(block) for block in mock_blocks.block_list if int(block.get('number')) != 0]

        # mess up the block hashes so we can see recalc fix them.
        for index, block in enumerate(block_list):
            # don't mess with the first block becausae we're going to use it as our correct "missing" block
            if index == 0:
                continue

            # compute an incorrect block hash, can be anything
            h = hashlib.sha3_256()
            h.update(f'testing_{index}'.encode())
            hash = h.hexdigest()
            block['hash'] = hash


            # if this is the second block we want to mess up the previous hash because it shouldn't match index 0 anymore
            if index == 1:
                h = hashlib.sha3_256()
                h.update('previous'.encode())
                block['previous'] = h.hexdigest()
            else:
                # for every other block make the previous block's previous hash value the value of the block's hash
                block['previous'] = block_list[index - 1]['hash']

        # add all the blocks into storage, bad hashes and all
        for block in block_list:
            self.missing_blocks_handler.process_block(block)

        # start at index 0 which is mocked as the "missing block" we just added into storage
        starting_block_number = block_list[0].get('number')
        # run recalc block hashes
        tasks = asyncio.gather(
            self.missing_blocks_handler.recalc_block_hashes(starting_block_number=starting_block_number)
        )
        self.loop.run_until_complete(tasks)

        # make sure recalc block hashes made the hashes correct again
        for block in proper_block_list:
            block_num = block.get('number')
            stored_block = self.missing_blocks_handler.block_storage.get_block(v=int(block_num))
            self.assertEqual(block.get('hash'), stored_block.get('hash'))
            self.assertEqual(block.get('previous'), stored_block.get('previous'))
            self.assertDictEqual(block.get('minted'), stored_block.get('minted'))

        # events were created
        events = os.listdir(self.missing_blocks_handler.event_writer.root)
        self.assertEqual(3, len(events))


class TestMissingBlocksWriter(TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.test_dir = os.path.abspath('./.lamden')
        self.missing_blocks_dir = os.path.join(self.test_dir, "missing_blocks")
        self.missing_blocks_filename = "missing_blocks.json"

        self.full_filename_path = os.path.join(self.missing_blocks_dir, self.missing_blocks_filename)

        self.create_directories()

        self.missing_blocks_writer: MissingBlocksWriter = None

    def tearDown(self):
        try:
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.close()
        except RuntimeError:
            pass

    def create_missing_blocks_writer(self):
        self.missing_blocks_writer = MissingBlocksWriter(
            root=self.test_dir
        )

    def create_directories(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

        os.makedirs(self.test_dir)

    def test_INSTANCE_init__creates_all_properties(self):
        # if the missing blocks directory exists, remove it so we can test it gets created
        if os.path.exists(self.missing_blocks_dir):
            shutil.rmtree(self.missing_blocks_dir)

        self.create_missing_blocks_writer()

        # root dir is stored as passed
        self.assertEqual(self.test_dir, self.missing_blocks_writer.root)

        # directories are created as they should
        self.assertEqual(self.missing_blocks_dir, self.missing_blocks_writer.missing_blocks_dir)
        self.assertEqual(self.full_filename_path, self.missing_blocks_writer.filename_path)

        # missing_blocks directory is created
        self.assertTrue(os.path.exists(self.missing_blocks_dir))

    def test_PRIVATE_METHOD_validate_blocks_list__raises_ValueError_if_blocks_list_is_None(self):
        self.create_missing_blocks_writer()

        blocks_list = None

        with self.assertRaises(ValueError) as err:
            self.missing_blocks_writer._validate_blocks_list(blocks_list=blocks_list)
            self.assertEqual("The provided list is None", str(err))

    def test_PRIVATE_METHOD_validate_blocks_list__raises_ValueError_if_blocks_list_no_list_instance(self):
        self.create_missing_blocks_writer()

        blocks_list = {}

        with self.assertRaises(ValueError) as err:
            self.missing_blocks_writer._validate_blocks_list(blocks_list=blocks_list)
            self.assertEqual("The provided blocks is not a list", str(err))

    def test_PRIVATE_METHOD_validate_blocks_list__raises_ValueError_if_blocks_list_is_empty(self):
        self.create_missing_blocks_writer()

        blocks_list = []

        with self.assertRaises(ValueError) as err:
            self.missing_blocks_writer._validate_blocks_list(blocks_list=blocks_list)
            self.assertEqual("The provided list is empty", str(err))

    def test_PRIVATE_METHOD_validate_blocks_list__rasies_NO_errors_if_list_has_items(self):
        self.create_missing_blocks_writer()

        blocks_list = ["1682939321560636160", "8520679865965181957", "2156250479259241801"]

        try:
            self.missing_blocks_writer._validate_blocks_list(blocks_list=blocks_list)
        except Exception:
            self.fail("This should not cause an exception.")

    def test_PRIVATE_METHOD_validate_block_strings__raises_ValueError_if_list_item_not_string(self):
        self.create_missing_blocks_writer()

        blocks_list = ["1682939321560636160", 8520679865965181957]

        with self.assertRaises(ValueError) as err:
            self.missing_blocks_writer._validate_block_strings(blocks_list=blocks_list)
            self.assertEqual("The provided list must contain only strings", str(err))

    def test_PRIVATE_METHOD_validate_block_strings__raises_No_errors_if_list_items_all_string(self):
        self.create_missing_blocks_writer()

        blocks_list = ["1682939321560636160", "8520679865965181957", "2156250479259241801"]

        try:
            self.missing_blocks_writer._validate_block_strings(blocks_list=blocks_list)
        except Exception:
            self.fail("This should not cause an exception.")

    def test_PRIVATE_METHOD_check_file_exists__raises_FileExistsError_if_file_exists(self):
        self.create_missing_blocks_writer()

        blocks_list = ["1682939321560636160", "8520679865965181957", "2156250479259241801"]

        with open(self.missing_blocks_writer.filename_path, "w") as f:
            json.dump(blocks_list, f)

        with self.assertRaises(FileExistsError) as err:
            self.missing_blocks_writer._check_file_exists(path=self.missing_blocks_writer.filename_path)
            self.assertEqual("missing_blocks.json already exists in the specified directory", str(err))

    def test_PRIVATE_METHOD_check_file_exists__raises_FileExistsError_if_file_exists(self):
        self.create_missing_blocks_writer()

        try:
            self.missing_blocks_writer._check_file_exists(path=self.missing_blocks_writer.filename_path)
        except FileExistsError:
            self.fail("This should not cause an exception.")

    def test_METHOD_write_missing_blocks__writes_file(self):
        self.create_missing_blocks_writer()

        blocks_list = ["1682939321560636160", "8520679865965181957", "2156250479259241801"]

        self.missing_blocks_writer.write_missing_blocks(blocks_list=blocks_list)

        self.assertTrue(os.path.exists(self.missing_blocks_writer.filename_path))

    def test_METHOD_write_missing_blocks__force_causes_no_FileExistsError_error(self):
        self.create_missing_blocks_writer()

        blocks_list = ["1682939321560636160", "8520679865965181957", "2156250479259241801"]

        with open(self.missing_blocks_writer.filename_path, "w") as f:
            json.dump(blocks_list, f)

        try:
            self.missing_blocks_writer.write_missing_blocks(blocks_list=blocks_list, force=True)
        except FileExistsError:
            self.fail("This should not cause an exception.")

        self.assertTrue(os.path.exists(self.missing_blocks_writer.filename_path))

    def test_METHOD_write_missing_blocks__raises_FileExistsError_exception_if_no_force_and_file_exists(self):
        self.create_missing_blocks_writer()

        blocks_list = ["1682939321560636160", "8520679865965181957", "2156250479259241801"]

        with open(self.missing_blocks_writer.filename_path, "w") as f:
            json.dump(blocks_list, f)

        with self.assertRaises(FileExistsError) as err:
            self.missing_blocks_writer.write_missing_blocks(blocks_list=blocks_list)
            self.assertEqual("missing_blocks.json already exists in the specified directory", str(err))
