from unittest import TestCase
from pathlib import Path
import shutil

from tests.integration.mock.local_node_network import LocalNodeNetwork

import asyncio
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

class TestNetwork(TestCase):
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
        task = asyncio.ensure_future(self.network.start_all_nodes())
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
        for i in range(num_of_blocks):
            block_num = i + 1
            block = {
                'number': block_num,
                'hlc_timestamp': str(block_num),
                'hash': str(block_num),
                'processed': {
                    'hash': str(block_num)
                }
            }
            for tn in self.network.all_nodes:
                tn.node.blocks.store_block(block=dict(block))
                tn.node.update_block_db(block=block)

    def test_new_peer_can_catchup_blocks_to_block_height_of_highest_node_block_height(self):
        self.network.create_new_network(
            num_of_masternodes=1,
            num_of_delegates=1
        )

        self.add_blocks_to_network(num_of_blocks=5)
        self.assertEqual(5, self.network.masternodes[0].node.get_current_height())

        self.network.add_new_node_to_network(
            node_type="delegate"
        )

        existing_node = self.network.masternodes[0]
        new_node = self.network.delegates[1]

        self.async_sleep(25)

        self.assertEqual(existing_node.latest_block_height, new_node.latest_block_height)
    '''
    def test_new_node_state_is_the_same_as_peers_after_catchup(self):
        self.network.create_new_network(
            num_of_masternodes=1,
            num_of_delegates=1
        )

        self.add_blocks_to_network(num_of_blocks=5)
        self.assertEqual(5, self.network.masternodes[0].node.get_current_height())

        self.network.add_new_node_to_network(
            node_type="delegate"
        )

        existing_node = self.network.masternodes[0]
        new_node = self.network.delegates[1]

        self.async_sleep(25)

        self.assertEqual(existing_node.latest_block_height, new_node.latest_block_height)
        '''

