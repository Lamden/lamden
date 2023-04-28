from tests.integration.mock.local_node_network import LocalNodeNetwork
from tests.integration.mock.local_node_network import ThreadedNode
from tests.integration.mock.mock_data_structures import MockBlocks
from unittest import TestCase
import asyncio
import copy
import uvloop
from contracting.db.encoder import decode
import time

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

        self.network = LocalNodeNetwork()

    def tearDown(self):
        task = asyncio.ensure_future(self.network.stop_all_nodes())
        while not task.done():
            self.loop.run_until_complete(asyncio.sleep(0.1))

        try:
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.close()
        except RuntimeError:
            pass

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def add_blocks_to_network(self, num_of_blocks):
        new_blocks = copy.copy(MockBlocks(num_of_blocks=num_of_blocks))
        for i in range(num_of_blocks):
            new_block = new_blocks.get_block_by_index(index=i)
            for tn in self.network.all_nodes:
                tn.node.blocks.store_block(block=copy.deepcopy(new_block))
                tn.node.update_block_db(block=new_block)
                tn.node.apply_state_changes_from_block(block=new_block)
        return new_blocks

    def mock_get_previous_block(self, v=None):
        return None


    def test_new_peer_can_catchup_blocks_to_block_height_of_highest_node_block_height_and_state_is_correct(self):
        self.network.create_new_network(
            num_of_masternodes=2,
            network_await_connect_all_timeout=2
        )

        for i in range(5):
            self.network.send_tx_to_random_masternode()
            self.async_sleep(1)

        new_node = self.network.add_new_node_to_network(join=True, network_await_connect_all_timeout=2)
        existing_nodes = self.network.masternodes[:2]

        while not new_node.node.started:
            self.async_sleep(1)

        for node in existing_nodes:
            self.assertEqual(node.node.get_current_height(), new_node.node.get_current_height())

        self.assertTrue(new_node.node.started)

        for node in existing_nodes:
            for key in node.raw_driver.keys():
                expected_value = node.get_smart_contract_value(key=key)
                actual_value = new_node.get_smart_contract_value(key=key)

                # add the new_node's vk into the members list. if there were a real situation it would have this from
                # a block but we mocked the catchup.

                if key == 'masternodes.S:members':
                    actual_value.append(new_node.vk)

                self.assertEqual(expected_value, actual_value)

    def test_node_shuts_down_if_errors_in_catchup(self):
        self.network.create_new_network(
            num_of_masternodes=2,
            network_await_connect_all_timeout=2
        )

        for i in range(5):
            self.network.send_tx_to_random_masternode()

        self.network.await_all_nodes_done_processing(block_height=6)

        # mock it so each node acts like it doesn't have the block.
        for node in self.network.masternodes:
            node.network.block_storage.get_previous_block = self.mock_get_previous_block

        self.async_sleep(2)

        new_node = self.network.add_new_node_to_network(join=True, network_await_connect_all_timeout=2)

        # Wait for node to start
        start_time = time.time()
        while not new_node.node_started:
            if time.time() - start_time > 10:
                self.fail("Timed out waiting for Node to start.")
            self.async_sleep(0)

        # Node should fail catchup as no nodes will respond with blocks

        # Wait for node to fail and stop
        start_time = time.time()
        while new_node.node_started:
            if time.time() - start_time > 10:
                self.fail("Timed out waiting for Node to stop.")
            self.async_sleep(0)

        self.assertFalse(new_node.node_started)
