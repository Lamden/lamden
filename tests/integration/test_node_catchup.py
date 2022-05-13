from unittest import TestCase
from pathlib import Path
import shutil
import copy

from tests.integration.mock.local_node_network import LocalNodeNetwork
from tests.integration.mock.mock_data_structures import MockBlocks

import asyncio
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

class TestNewNodeCatchup(TestCase):
    def setUp(self):
        try:
            self.loop = asyncio.get_event_loop()

            if self.loop.is_closed():
                self.loop = None
        except:
            self.loop = None
        finally:
            if not self.loop:
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)

        self.network = LocalNodeNetwork(
            genesis_path=Path(f'{Path.cwd()}/mock')
        )

    def tearDown(self):
        task = asyncio.ensure_future(self.network.stop_all_nodes())
        while not task.done():
            self.loop.run_until_complete(asyncio.sleep(0.1))

        if not self.loop.is_closed():
            self.loop.stop()
            self.loop.close()

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def add_blocks_to_network(self, num_of_blocks):
        new_blocks = copy.copy(MockBlocks(num_of_blocks=num_of_blocks))
        for i in range(num_of_blocks):
            block_num = i + 1

            for tn in self.network.all_nodes:
                new_block = new_blocks.get_block(num=block_num)
                tn.node.blocks.store_block(block=copy.deepcopy(new_block))
                tn.node.update_block_db(block=new_block)
                tn.node.apply_state_changes_from_block(block=new_block)
        return new_blocks

    def test_testcase_can_preload_blocks(self):
        self.network.create_new_network(
            num_of_masternodes=1,
            num_of_delegates=0
        )

        self.add_blocks_to_network(num_of_blocks=5)
        self.assertEqual(5, self.network.masternodes[0].node.get_current_height())

    def test_testcase_preloading_can_add_state(self):
        self.network.create_new_network(
            num_of_masternodes=1,
            num_of_delegates=0
        )

        mock_blocks = self.add_blocks_to_network(num_of_blocks=1)
        self.assertEqual(1, self.network.masternodes[0].node.get_current_height())

        node = self.network.all_nodes[0]

        for vk, amount in mock_blocks.internal_state.items():
            print(f'node vk: {node.vk}')
            print(vk, str(amount))
            state_amount = node.get_smart_contract_value(key=f'currency.balances:{vk}')
            self.assertEqual(amount, state_amount)

    def test_new_peer_can_catchup_blocks_to_block_height_of_highest_node_block_height(self):
        self.network.create_new_network(
            num_of_masternodes=1,
            num_of_delegates=1
        )

        blocks = self.add_blocks_to_network(num_of_blocks=5)

        self.network.add_new_node_to_network(
            node_type="delegate"
        )

        existing_node = self.network.masternodes[0]
        new_node = self.network.delegates[1]

        blocks.add_block()
        new_block = blocks.get_block(num=6)
        new_node.node.last_minted_block = new_block

        self.async_sleep(30)

        self.assertEqual(existing_node.latest_block_height, new_node.latest_block_height)

    def test_new_node_state_is_the_same_as_peers_after_catchup(self):
        self.network.create_new_network(
            num_of_masternodes=1,
            num_of_delegates=1
        )

        blocks = self.add_blocks_to_network(num_of_blocks=5)

        self.network.add_new_node_to_network(
            node_type="delegate"
        )

        new_node = self.network.delegates[1]

        self.async_sleep(25)

        blocks.add_block()
        new_block = blocks.get_block(num=6)
        new_node.node.last_minted_block = new_block
        new_node.node.apply_state_changes_from_block(block=new_block)

        self.async_sleep(15)

        for vk, amount in blocks.internal_state.items():
            state_amount = new_node.get_smart_contract_value(key=f'currency.balances:{vk}')
            self.assertEqual(amount, state_amount)






