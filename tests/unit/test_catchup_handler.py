import json
from unittest import TestCase
from lamden.storage import BlockStorage, NonceStorage, LATEST_BLOCK_HASH_KEY, LATEST_BLOCK_HEIGHT_KEY
from lamden.crypto.wallet import Wallet
from contracting.db.driver import ContractDriver, FSDriver
from lamden.nodes.catchup import CatchupHandler
from tests.integration.mock.mock_data_structures import MockBlocks
from contracting.db.encoder import encode

import os
import shutil
import json
import asyncio

# MOCK NETWORK
class Network:
    def __init__(self):
        self.peers = []

    def get_highest_peer_block(self) -> int:
        current_highest_block = 0

        for peer in self.peers:
            block_list = list(peer.blocks.keys())
            block_list.sort()

            if len(block_list) > 0:
                latest_block_number = int(block_list[-1])

            if latest_block_number > current_highest_block:
                current_highest_block = latest_block_number

        return current_highest_block

    def get_all_connected_peers(self):
        return self.peers

    def add_peer(self, blocks={}):
        self.peers.append(MockPeer(blocks=blocks))

    def get_peer(self, vk: str):
        for peer in self.peers:
            if peer.server_vk == vk:
                return peer

    def refresh_approved_peers_in_cred_provider(self):
        pass

class MockPeer:
    def __init__(self, blocks={}):
        self.blocks = blocks

        wallet = Wallet()
        self.server_vk = wallet.verifying_key

    @property
    def block_list(self):
        return [self.blocks[key] for key in sorted(self.blocks.keys(), key=int)]

    def find_block(self, block_num: str) -> dict:
        return self.blocks.get(block_num, None)

    async def get_block(self, block_num: int) -> (dict, None):
        block = self.find_block(str(block_num))
        block = json.loads(encode(block))
        if block is None:
            return  {'block_info': None}

        return {'block_info': block}

    async def get_previous_block(self, block_num: int) -> (dict, None):
        block_list = list(self.blocks.keys())
        block_list.sort()

        try:
            index = block_list.index(str(block_num))
            if index == 0:
                return {'block_info': None}

            block = self.find_block(block_list[index - 1])
            block = json.loads(encode(block))
            return {'block_info': block}
        except ValueError:
            return {'block_info': None}

    async def get_latest_block_info(self):
        latest_block = self.block_list[-1]

        block_num = latest_block.get('number')
        block_hash = latest_block.get('hash')
        hlc_timestamp = latest_block.get("hlc_timestamp")

        return {'block_info': {
            'number': block_num,
            'hash': block_hash,
            'hlc_timestamp': hlc_timestamp
        }}

class TestCatchupHandler(TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.test_dir = os.path.abspath('./.lamden')

        self.create_directories()

        self.block_storage = BlockStorage(root=self.test_dir)
        self.state_driver = FSDriver(root=self.test_dir)
        self.contract_driver = ContractDriver(driver=self.state_driver)
        self.nonce_storage = NonceStorage(root=self.test_dir)
        self.mock_network = Network()

        self.catchup_handler: CatchupHandler = None

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

    def add_peers_to_network(self, amount, blocks={}):
        blocks = dict(blocks)
        for i in range(amount):
            self.mock_network.add_peer(blocks=blocks)

    def create_catchup_handler(self, hardcoded_peers: bool = False):
        self.catchup_handler = CatchupHandler(
            contract_driver=self.contract_driver,
            block_storage=self.block_storage,
            nonce_storage=self.nonce_storage,
            network=self.mock_network,
            hardcoded_peers=hardcoded_peers
        )

    def test_PROPERTY_latest_block_number__returns_correct_block_height(self):
        self.create_catchup_handler()

        num_of_blocks=10
        mock_blocks = MockBlocks(num_of_blocks=num_of_blocks)

        block_number = int(mock_blocks.block_list[-1]['number'])

        for block in mock_blocks.block_list:
            self.catchup_handler.block_storage.store_block(block)

        self.assertEqual(block_number, self.catchup_handler.latest_block_number)

    def test_PROPERTY_latest_block_number__returns_0_if_None(self):
        self.create_catchup_handler()

        self.assertEqual(0, self.catchup_handler.latest_block_number)


    def test_METHOD_get_random_catchup_peer__returns_a_Peer(self):
        self.add_peers_to_network(10)
        self.create_catchup_handler()

        self.catchup_handler.catchup_peers = self.mock_network.peers

        catch_peers_vk_list = [peer.server_vk for peer in self.catchup_handler.catchup_peers]
        random_peer = self.catchup_handler.get_random_catchup_peer(vk_list=catch_peers_vk_list)

        self.assertIsInstance(random_peer, MockPeer)

    def test_METHOD_get_random_catchup_peer__returns_None_if_no_peers_in_list(self):
        self.add_peers_to_network(10)
        self.create_catchup_handler()

        catch_peers_vk_list = [peer.server_vk for peer in self.catchup_handler.catchup_peers]
        random_peer = self.catchup_handler.get_random_catchup_peer(vk_list=catch_peers_vk_list)

        self.assertIsNone(random_peer)

    def test_METHOD_safe_set_state_changes_and_rewards__sets_values_from_block(self):
        self.create_catchup_handler()

        expected_jeff_bal = '456'
        expected_stu_bal = '789'

        block = {
            'number': '10',
            'processed': {
                'state': [
                    {'key': 'currency.balances:jeff', 'value': {'__fixed__': '123'}},
                    {'key': 'catchup.testing', 'value': True},
                ]
            },
            'rewards': [
                {'key': 'currency.balances:jeff', 'value': {'__fixed__': expected_jeff_bal}},
                {'key': 'currency.balances:stu', 'value': {'__fixed__': '789'}}
            ]
        }

        self.catchup_handler.safe_set_state_changes_and_rewards(block=block)

        jeff_bal = self.contract_driver.driver.get('currency.balances:jeff')
        stu_bal = self.contract_driver.driver.get('currency.balances:stu')
        testing_val = self.contract_driver.driver.get('catchup.testing')

        self.assertEqual(expected_jeff_bal, str(jeff_bal))
        self.assertEqual(expected_stu_bal, str(stu_bal))
        self.assertTrue(testing_val)

    def test_METHOD_safe_set_state_changes_and_rewards__does_not_overwrite_if_value_set_from_higher_block(self):
        self.create_catchup_handler()

        expected_jeff_bal = '456'
        expected_stu_bal = '789'

        block_10 = {
            'number': '10',
            'processed': {
                'state': [
                    {'key': 'currency.balances:jeff', 'value': {'__fixed__': '123'}},
                    {'key': 'catchup.testing:1', 'value': True},
                ]
            },
            'rewards': [
                {'key': 'currency.balances:jeff', 'value': {'__fixed__': expected_jeff_bal}},
                {'key': 'currency.balances:stu', 'value': {'__fixed__': expected_stu_bal}}
            ]
        }

        block_9 = {
            'number': '9',
            'processed': {
                'state': [
                    {'key': 'currency.balances:jeff', 'value': {'__fixed__': '111'}},
                    {'key': 'catchup.testing:1', 'value': False},
                    {'key': 'catchup.testing:2', 'value': True},
                ]
            },
            'rewards': [
                {'key': 'currency.balances:jeff', 'value': {'__fixed__': '222'}},
                {'key': 'currency.balances:stu', 'value': {'__fixed__': '333'}}
            ]
        }

        self.catchup_handler.safe_set_state_changes_and_rewards(block=block_10)
        self.catchup_handler.safe_set_state_changes_and_rewards(block=block_9)

        jeff_bal = self.contract_driver.driver.get('currency.balances:jeff')
        stu_bal = self.contract_driver.driver.get('currency.balances:stu')
        testing_1_val = self.contract_driver.driver.get('catchup.testing:1')
        testing_2_val = self.contract_driver.driver.get('catchup.testing:2')

        self.assertEqual(expected_jeff_bal, str(jeff_bal))
        self.assertEqual(expected_stu_bal, str(stu_bal))
        self.assertTrue(testing_1_val)
        self.assertTrue(testing_2_val)

    def test_METHOD_save_nonce_information_saves_nonce_info_from_block(self):
        self.create_catchup_handler()

        sender = 'jeff'
        processor = 'stu'
        expected_nonce = 10

        block = {
            'processed': {
                'transaction': {
                    'payload': {
                        'sender': sender,
                        'processor': processor,
                        'nonce': expected_nonce
                    }
                }
            }
        }

        self.catchup_handler.save_nonce_information(block=block)

        nonce = self.nonce_storage.get_nonce(sender=sender, processor=processor)

        self.assertEqual(expected_nonce, nonce)

    def test_METHOD_process_block__can_process_a_block_into_storage(self):
        self.create_catchup_handler()

        mock_blocks = MockBlocks(num_of_blocks=2)
        block = json.loads(encode(mock_blocks.latest_block))

        self.catchup_handler.process_block(block=block)

        # Did Store Block
        block_number = block.get('number')
        block_hash = block.get('hash')
        tx_hash = block['processed'].get('hash')

        self.assertIsNotNone(self.block_storage.get_block(v=block_number))
        self.assertIsNotNone(self.block_storage.get_block(v=block_hash))
        self.assertIsNotNone(self.block_storage.get_tx(h=tx_hash))

        # Did Set Nonce
        sender = block['processed']['transaction']['payload']['sender']
        processor = block['processed']['transaction']['payload']['processor']
        expected_nonce = 0

        self.assertEqual(expected_nonce, self.nonce_storage.get_nonce(sender, processor))

        # Did Save State
        for sc in block['processed']['state']:
            block_value = encode(sc.get('value'))
            saved_val = encode(self.contract_driver.driver.get(sc.get('key')))
            self.assertEqual(block_value, saved_val)

    def test_METHOD_process_block__returns_if_block_exists(self):
        self.create_catchup_handler()

        mock_blocks = MockBlocks(num_of_blocks=2)
        block = json.loads(encode(mock_blocks.latest_block))
        block_number = block.get('number')

        self.catchup_handler.process_block(block=block)

        # This would cause an error if the method didn't return right away
        self.catchup_handler.process_block(
            block={'number': block_number}
        )

    def test_METHOD_source_block_from_peers__can_get_a_specific_block_from_peers(self):
        mock_blocks = MockBlocks(num_of_blocks=5)
        latest_block_number = mock_blocks.latest_block_number

        self.add_peers_to_network(amount=5, blocks=mock_blocks.blocks)

        self.create_catchup_handler()
        self.catchup_handler.catchup_peers = self.mock_network.peers

        tasks = asyncio.gather(
            self.catchup_handler.source_block_from_peers(block_num=int(latest_block_number), fetch_type='specific')
        )
        res = self.loop.run_until_complete(tasks)

        block = res[0]

        self.assertIsNotNone(block)
        self.assertEqual(latest_block_number, block.get('number'))

    def test_METHOD_source_block_from_peers__can_get_a_previous_block_from_peers(self):
        mock_blocks = MockBlocks(num_of_blocks=5)
        latest_block_number = mock_blocks.latest_block_number
        previous_block_number = mock_blocks.block_numbers_list[-2]

        self.add_peers_to_network(amount=5, blocks=mock_blocks.blocks)

        self.create_catchup_handler()
        self.catchup_handler.catchup_peers = self.mock_network.peers

        tasks = asyncio.gather(
            self.catchup_handler.source_block_from_peers(block_num=int(latest_block_number), fetch_type='previous')
        )
        res = self.loop.run_until_complete(tasks)

        block = res[0]

        self.assertIsNotNone(block)
        self.assertEqual(previous_block_number, block.get('number'))

    def test_METHOD_get_previous_block__can_get_a_previous_block(self):
        mock_blocks = MockBlocks(num_of_blocks=5)
        latest_block_number = mock_blocks.latest_block_number
        previous_block_number = mock_blocks.block_numbers_list[-2]

        self.add_peers_to_network(amount=5, blocks=mock_blocks.blocks)

        self.create_catchup_handler()
        self.catchup_handler.catchup_peers = self.mock_network.peers

        tasks = asyncio.gather(
            self.catchup_handler.get_previous_block(block_num=latest_block_number)
        )
        res = self.loop.run_until_complete(tasks)

        block = res[0]

        self.assertIsNotNone(block)
        self.assertEqual(previous_block_number, block.get('number'))

    def test_METHOD_get_highest_network_block__can_return_the_latest_block_of_all_peers(self):
        mock_blocks = MockBlocks(num_of_blocks=5)
        latest_block_number = mock_blocks.latest_block_number

        # Add 3 peers to the network with all blocks
        self.add_peers_to_network(amount=3, blocks=mock_blocks.blocks)

        # Remove 1 block and give that to 2 new peers
        mock_blocks.blocks.pop(mock_blocks.latest_block_number)
        self.add_peers_to_network(amount=2, blocks=mock_blocks.blocks)

        self.create_catchup_handler()
        self.catchup_handler.catchup_peers = self.mock_network.peers

        tasks = asyncio.gather(
            self.catchup_handler.get_highest_network_block()
        )
        res = self.loop.run_until_complete(tasks)

        # This block should be the block that the first 3 peers added have.
        block = res[0]

        self.assertIsNotNone(block)
        self.assertEqual(latest_block_number, block.get('number'))


    def test_METHOD_run__can_catchup_all_blocks_from_peers(self):
        num_of_blocks=10
        mock_blocks = MockBlocks(num_of_blocks=num_of_blocks)
        blocks_list = mock_blocks.block_numbers_list

        # Give nodes a different number of blocks to simulate all nodes not having all blocks
        # Each new node has 1 less block than the last
        self.add_peers_to_network(amount=num_of_blocks//2 + 1, blocks=mock_blocks.blocks)
        for i in range(num_of_blocks//2 - 1):
            mock_blocks.blocks.pop(mock_blocks.latest_block_number)
            self.add_peers_to_network(amount=1, blocks=mock_blocks.blocks)

        self.create_catchup_handler()

        tasks = asyncio.gather(
            self.catchup_handler.run()
        )
        self.loop.run_until_complete(tasks)

        for block_num in blocks_list:
            if int(block_num) != 0:
                self.assertIsNotNone(self.block_storage.get_block(block_num))


    def test_METHOD_run__does_not_run_if_at_latest(self):
        num_of_blocks=10
        mock_blocks = MockBlocks(num_of_blocks=num_of_blocks)
        self.add_peers_to_network(amount=5, blocks=mock_blocks.blocks)

        self.create_catchup_handler()
        self.catchup_handler.block_storage.store_block(mock_blocks.block_list[-1])

        tasks = asyncio.gather(
            self.catchup_handler.run()
        )
        res = self.loop.run_until_complete(tasks)

        self.assertEqual('not_run', res[0])

    def test_METHOD_run__can_catchup_from_network_latest_to_local_latest(self):
        num_of_blocks=10
        mock_blocks = MockBlocks(num_of_blocks=num_of_blocks)
        latest_block_num = mock_blocks.latest_block_number

        self.add_peers_to_network(amount=5, blocks=mock_blocks.blocks)

        for block_num in mock_blocks.block_numbers_list[-5:]:
            mock_blocks.blocks.pop(block_num)

        self.create_catchup_handler()

        for block_num in mock_blocks.block_numbers_list:
            if int(block_num) != 0:
                self.catchup_handler.process_block(block=mock_blocks.blocks.get(block_num))


        tasks = asyncio.gather(
            self.catchup_handler.run()
        )
        self.loop.run_until_complete(tasks)

        self.assertEqual(int(latest_block_num), self.catchup_handler.latest_block_number)

    def test_METHOD_run__hardcoded_peers_filters_out_peers(self):
        num_of_blocks=10
        mock_blocks = MockBlocks(num_of_blocks=num_of_blocks)

        self.add_peers_to_network(amount=5, blocks=mock_blocks.blocks)

        for block_num in mock_blocks.block_numbers_list[-5:]:
            mock_blocks.blocks.pop(block_num)

        # Set to only use specific ones
        self.create_catchup_handler(hardcoded_peers=True)
        # Set valid ones to peer[0]
        self.catchup_handler.valid_peers = [self.mock_network.peers[0].server_vk]

        tasks = asyncio.gather(
            self.catchup_handler.run()
        )
        self.loop.run_until_complete(tasks)

        self.assertEqual(1, len(self.catchup_handler.catchup_peers))




