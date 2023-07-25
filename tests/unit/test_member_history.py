from unittest import TestCase
from tests.integration.mock.mock_data_structures import MockBlocks

from lamden.storage import BlockStorage
from lamden.crypto.wallet import Wallet
from lamden.crypto.canonical import hash_members_list

from lamden.nodes.member_history import MemberHistoryHandler


import os
import shutil
import json
import asyncio

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

        self.wallet = Wallet()
        self.server_vk = self.wallet.verifying_key

    @property
    def block_list(self):
        return [self.blocks[key] for key in sorted(self.blocks.keys(), key=int)]

    async def get_member_history_next(self, block_num: int):
        return_info = {'member_history_info': None}

        for block in self.block_list:
            number = int(block.get('number'))

            if number > block_num:
                if number == 0:
                    state_changes = block.get('genesis')
                else:
                    state_changes = block['processed'].get('state')

                for state_change in state_changes:
                    if state_change.get('key') == 'masternodes.S:members':
                        members_list = state_change.get('value')
                        members_list_hash = hash_members_list(members=members_list)

                        msg = f'{members_list_hash}{str(number)}'
                        signature = self.wallet.sign(msg=msg)

                        return {
                            'member_history_info': {
                                'number': str(number),
                                'members_list': state_change.get('value'),
                                'signature': signature
                            }
                        }

        return return_info


class TestMemberHistoryHandler(TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.test_dir = os.path.abspath('./.lamden')

        self.create_directories()

        self.block_storage = BlockStorage(root=self.test_dir)
        self.mock_network = Network()

        self.member_history_handler: MemberHistoryHandler = None

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

    def create_handler(self, hardcoded_peers: bool = False):
        self.member_history_handler = MemberHistoryHandler(
            block_storage=self.block_storage,
            network=self.mock_network
        )

    def test_INSTANCE__can_create_instance(self):
        member_history_handler = MemberHistoryHandler(
            block_storage=self.block_storage,
            network=self.mock_network
        )

        self.assertIsInstance(member_history_handler, MemberHistoryHandler)
        self.assertIsNotNone(member_history_handler.block_storage)
        self.assertIsNotNone(member_history_handler.network)

    def test_METHOD_source_history_from_peers__raises_ValueError_if_no_peers(self):
        self.create_handler()

        with self.assertRaises(ValueError):
            tasks = asyncio.gather(
                self.member_history_handler.source_history_from_peers(fetch_type='next', block_num=-1)
            )
            res = self.loop.run_until_complete(tasks)


    def test_METHOD_source_history_from_peers__can_get_consensus_item(self):
        self.create_handler()
        mock_blocks = MockBlocks(num_of_blocks=10)

        for i in range(3):
            self.mock_network.add_peer(blocks=mock_blocks.blocks)

        self.member_history_handler.peers = self.mock_network.get_all_connected_peers()

        tasks = asyncio.gather(
            self.member_history_handler.source_history_from_peers(fetch_type='next', block_num=-1)
        )
        res = self.loop.run_until_complete(tasks)[0]

        block_num = res.get('number')
        members_list = res.get('members_list')

        self.assertIsNotNone(block_num)
        self.assertIsNotNone(members_list)

    def test_METHOD_get_next_history_item__can_get_next_consensus_item(self):
        self.create_handler()
        mock_blocks = MockBlocks(num_of_blocks=10)

        for i in range(3):
            self.mock_network.add_peer(blocks=mock_blocks.blocks)

        self.member_history_handler.peers = self.mock_network.get_all_connected_peers()

        tasks = asyncio.gather(
            self.member_history_handler.get_next_history_item(block_num=-1)
        )
        res = self.loop.run_until_complete(tasks)[0]

        block_num = res.get('number')
        members_list = res.get('members_list')

        self.assertEqual('0', block_num)
        self.assertIsNotNone(mock_blocks.initial_members.get('masternodes'), members_list)

    def test_METHOD_get_next_history_item__returns_None_if_block_num_is_None(self):
        self.create_handler()

        tasks = asyncio.gather(
            self.member_history_handler.get_next_history_item()
        )
        res = self.loop.run_until_complete(tasks)[0]

        self.assertIsNone(res)

    def test_METHOD_catchup_history__can_catchup_all_history_from_peers(self):
        self.create_handler()
        mock_blocks = MockBlocks(num_of_blocks=10)
        current_members = mock_blocks.initial_members.get('masternodes')
        new_members = list(current_members)
        new_members.append(Wallet().verifying_key)

        # Add a state change into the last block that we should pickup
        mock_blocks.block_list[-1]['processed']['state'].append({
            'key': 'masternodes.S:members',
            'value': new_members
        })

        for i in range(3):
            self.mock_network.add_peer(blocks=mock_blocks.blocks)

        self.member_history_handler.peers = self.mock_network.get_all_connected_peers()
        self.member_history_handler.block_storage.member_history.set(
            block_num='0',
            members_list=current_members
        )

        tasks = asyncio.gather(
            self.member_history_handler.catchup_history()
        )
        self.loop.run_until_complete(tasks)

        members_list = self.block_storage.member_history.get(block_num='99999999999999999999')
        self.assertIsNotNone(new_members, members_list)

    def test_METHOD_create_member_history_from_blocks__can_rebuild_from_the_stored_blocks(self):
        self.create_handler()
        mock_blocks = MockBlocks(num_of_blocks=10)

        current_members = mock_blocks.initial_members.get('masternodes')
        new_members = list(current_members)
        new_members.append(Wallet().verifying_key)

        # Add a state change into the last block that we should pickup
        mock_blocks.block_list[-1]['processed']['state'].append({
            'key': 'masternodes.S:members',
            'value': new_members
        })

        for i in range(3):
            self.mock_network.add_peer(blocks=mock_blocks.blocks)

        self.member_history_handler.create_members_history_from_blocks()

        members_list = self.block_storage.member_history.get(block_num='99999999999999999999')
        self.assertIsNotNone(new_members, members_list)

