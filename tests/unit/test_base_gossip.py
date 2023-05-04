from lamden.nodes.base import Node
from lamden.storage import BlockStorage, FSDriver, ContractDriver, NonceStorage
from lamden.crypto.wallet import Wallet
from lamden.nodes.events import EventWriter

from contracting.db.encoder import encode

import os
import asyncio
import shutil
from unittest import TestCase
import json

from tests.integration.mock.mock_data_structures import MockBlocks


class MockPeer:
    def __init__(self, blocks:list = []):
        self.blocks: list = blocks

        wallet = Wallet()
        self.server_vk = wallet.verifying_key

        self.connected = True
        self.running = True


    def find_block(self, v: int) -> dict:
        for index, value in enumerate(self.blocks):
            if v == int(value['number']):
                return value

    def get_previous_block(self, v: int):
        for index, value in enumerate(self.blocks):
            if v == int(value['number']):
                if index == 0:
                    return None
                return self.blocks[index - 1]

    async def stop(self):
        self.connected = False
        self.running = False

    async def gossip_new_block(self, block_num: str, previous_block_num: str) -> dict:
        message_block_num = block_num
        message_previous_block_num = previous_block_num

        if message_block_num is None or message_previous_block_num is None:
            return

        my_previous_block = self.get_previous_block(v=int(message_block_num))
        my_previous_block_number = my_previous_block.get('number')
        missing_block = None

        if int(my_previous_block_number) != int(message_previous_block_num):
            missing_block = my_previous_block_number

        return {"missing_block": missing_block}

class TestBaseGossip(TestCase):
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
        self.event_writer = EventWriter(root=os.path.join(self.test_dir, 'events'))
        self.wallet = Wallet()

        self.node: Node = None

    def tearDown(self):
        try:
            self.loop.run_until_complete(self.node.stop())
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.close()
        except RuntimeError:
            pass

    def create_directories(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

        os.makedirs(self.test_dir)

    def create_node(self):
        self.node = Node(
            blocks=self.block_storage,
            driver=self.contract_driver,
            event_writer=self.event_writer,
            wallet=self.wallet,
            nonces=self.nonce_storage
        )

    def add_peers(self, num_of_peers: int, blocks: list):
        for i in range(num_of_peers):
            peer_wallet = Wallet()
            peer_vk = peer_wallet.verifying_key
            peer = MockPeer(blocks=blocks)
            peer.connected = True
            self.node.network.peers[peer_vk] = peer

    def add_blocks_to_node(self, blocks: list, ignore: str = "-1"):
        for block in blocks:
            if block.get('number') == ignore:
                continue

            self.node.blocks.store_block(block=block)

    def test_INSTANCE_init__node_is_created(self):
        try:
            self.create_node()
        except Exception:
            self.fail("Should not cause exceptions")


        self.assertIsNotNone(self.node)

    def test_METHOD_gossip_about_new_block__creates_no_files_no_no_block_missing(self):
        self.create_node()
        mock_blocks = MockBlocks(num_of_blocks=10)
        latest_block = mock_blocks.get_latest_block()

        self.add_peers(num_of_peers=100, blocks=mock_blocks.block_list_encoded)
        self.add_blocks_to_node(blocks=mock_blocks.block_list_encoded)

        self.loop.run_until_complete(self.node.gossip_about_new_block(block=latest_block))

        self.assertFalse(os.listdir(self.node.missing_blocks_handler.missing_blocks_dir))

    def test_METHOD_gossip_about_new_block__creates_files_if_block_missing(self):
        self.create_node()
        mock_blocks = MockBlocks(num_of_blocks=10)
        latest_block = mock_blocks.get_latest_block()
        previous_block = mock_blocks.get_previous_block(block_num=latest_block.get('number'), block_list=mock_blocks.block_list_encoded)
        previous_block_number = previous_block.get('number')

        self.add_peers(num_of_peers=100, blocks=mock_blocks.block_list_encoded)
        self.add_blocks_to_node(blocks=mock_blocks.block_list_encoded, ignore=previous_block_number)

        self.loop.run_until_complete(self.node.gossip_about_new_block(block=latest_block))

        file_path = os.path.join(self.node.missing_blocks_handler.missing_blocks_dir, previous_block_number)
        self.assertTrue(os.path.exists(file_path))