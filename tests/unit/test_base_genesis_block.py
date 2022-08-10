from unittest import TestCase
import shutil
from pathlib import Path

from lamden.nodes.base import Node

from lamden.storage import BlockStorage, NonceStorage, set_latest_block_height
from contracting.db.driver import ContractDriver, FSDriver, InMemDriver
from lamden.nodes.filequeue import FileQueue

from lamden.crypto.wallet import Wallet

from tests.integration.mock.mock_data_structures import MockBlocks

from typing import List
from lamden.cli.start import resolve_genesis_block

import asyncio
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

class TestBaseGenesisBlock(TestCase):
    def setUp(self):
        self.current_path = Path.cwd()
        self.genesis_path = Path(f'{self.current_path.parent}/integration/mock')
        self.temp_storage = Path(f'{self.current_path}/temp_storage')

        self.genesis_block = resolve_genesis_block(Path(f'{self.current_path}/helpers/genesis_block.json'))

        try:
            shutil.rmtree(self.temp_storage)
        except FileNotFoundError:
            pass
        self.temp_storage.mkdir(exist_ok=True, parents=True)

        self.node: Node = None


    def tearDown(self):
        if self.node:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.node.stop())

            del self.node

    def create_node_instance(self, genesis=None) -> Node:
        node_wallet = Wallet()
        node_dir = Path(f'{self.temp_storage}/{node_wallet.verifying_key}')
        # node_state_dir = Path(f'{node_dir}/state')
        raw_driver = InMemDriver()
        contract_driver = ContractDriver(driver=raw_driver)
        block_storage = BlockStorage(root=node_dir)
        nonce_storage = NonceStorage(nonce_collection=Path(node_dir).joinpath('nonces'))

        tx_queue = FileQueue(root=node_dir)

        constitution = {
            'masternodes': [node_wallet.verifying_key],
            'delegates': [],
        }

        return Node(
            constitution=constitution,
            bootnodes={},
            socket_base="",
            wallet=node_wallet,
            socket_ports=self.create_socket_ports(index=0),
            driver=contract_driver,
            blocks=block_storage,
            genesis_block=genesis,
            tx_queue=tx_queue,
            testing=True,
            nonces=nonce_storage
        )

    def start_node(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.node.start())

    def create_socket_ports(self, index=0):
        return {
            'router': 19000 + index,
            'publisher': 19080 + index,
            'webserver': 18080 + index
        }

    def get_catchup_peers(self):
        return self.catchup_peers

    def mock_get_highest_peer_blocks(self):
        highest_block_num = 0
        for peer in self.catchup_peers:
            if peer.latest_block_number > highest_block_num:
                highest_block_num = peer.latest_block_number
        return highest_block_num

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def test_can_create_node_instance(self):
        self.node = self.create_node_instance()
        self.assertIsNotNone(self.node)

    def test_sets_start_new_network_to_TRUE_if_genesis_block_provided(self):
        self.node = self.create_node_instance(genesis=self.genesis_block)
        self.assertTrue(self.node.new_network_start)

    def test_sets_start_new_network_to_FALSE_if_genesis_block_NOT_provided(self):
        self.node = self.create_node_instance()
        self.assertFalse(self.node.new_network_start)

    def test_processes_genesis_info_into_state(self):
        self.node = self.create_node_instance(genesis=self.genesis_block)
        genesis_state = self.genesis_block.get('genesis')

        for state_change in genesis_state:
            self.assertIsNotNone(self.node.driver.get(state_change.get('key')))

    def test_store_genesis_block__can_store_state_from_a_genesis_block(self):
        self.node = self.create_node_instance()
        genesis_state = self.genesis_block.get('genesis')

        self.node.store_genesis_block(genesis_block=self.genesis_block)
        for state_change in genesis_state:
            self.assertIsNotNone(self.node.driver.get(state_change.get('key')))

    def test_store_genesis_block__returns_TRUE_if_successful(self):
        self.node = self.create_node_instance()

        self.assertTrue(self.node.store_genesis_block(genesis_block=self.genesis_block))

    def test_store_genesis_block__returns_FALSE_if_blocks_exist(self):
        self.node = self.create_node_instance()

        blocks = MockBlocks(num_of_blocks=1)
        block = blocks.get_block(num=0)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.node.hard_apply_block(block=block))

        self.assertFalse(self.node.store_genesis_block(genesis_block=self.genesis_block))
