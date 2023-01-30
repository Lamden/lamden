from tests.integration.mock.local_node_network import LocalNodeNetwork
from tests.integration.mock.local_node_network import ThreadedNode
from tests.integration.mock.mock_data_structures import MockBlocks
from unittest import TestCase
import asyncio
import copy
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

        self.network = LocalNodeNetwork()

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
            new_block = new_blocks.get_block_by_index(index=i)
            for tn in self.network.all_nodes:
                tn.node.blocks.store_block(block=copy.deepcopy(new_block))
                tn.node.update_block_db(block=new_block)
                tn.node.apply_state_changes_from_block(block=new_block)
        return new_blocks

    def test_new_peer_can_catchup_blocks_to_block_height_of_highest_node_block_height_and_state_is_correct(self):
        self.network.create_new_network(
            num_of_masternodes=2
        )

        for i in range(5):
            self.network.send_tx_to_random_masternode()
            self.async_sleep(1)

        new_node = self.network.add_new_node_to_network()
        existing_nodes = self.network.masternodes[:2]

        self.assertFalse(new_node.node.started)

        while not new_node.validation_queue.allow_append:
            self.async_sleep(1)

        self.async_sleep(5)

        for i in range(3):
            self.network.send_tx_to_masternode(existing_nodes[0].vk)
            self.async_sleep(3)

        while not new_node.node.started:
            self.async_sleep(1)

        # Let new node catchup
        self.async_sleep(7)

        for node in existing_nodes:
            self.assertEqual(node.node.get_current_height(), new_node.node.get_current_height())
        self.assertTrue(new_node.node.started)

        # NOTE: in real world new_node vk would be added by catchup because it's voted in by other nodes
        new_node.set_smart_contract_value(
            key='masternodes.S:members',
            value=new_node.get_smart_contract_value(key='masternodes.S:members') + [new_node.vk]
        )

        for node in existing_nodes:
            for key in node.raw_driver.keys():
                expected_value = node.get_smart_contract_value(key=key)
                actual_value = new_node.get_smart_contract_value(key=key)
                self.assertEqual(expected_value, actual_value)