from unittest import TestCase
from pathlib import Path

from tests.integration.mock.local_node_network import LocalNodeNetwork

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

    def test_masternode_can_receive_tx_and_send_to_other_nodes(self):
        self.network.create_new_network(
            num_of_masternodes=2,
            num_of_delegates=2
        )

        self.network.pause_all_queues()
        self.async_sleep(60)

        self.network.send_tx_to_random_masternode()

        self.async_sleep(30)

        for tn in self.network.all_nodes:
            self.assertEqual(1, len(tn.node.main_processing_queue))










