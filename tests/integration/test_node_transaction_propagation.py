import time
from unittest import TestCase
from pathlib import Path

from tests.integration.mock.local_node_network import LocalNodeNetwork
from lamden.utils.hlc import nanos_from_hlc_timestamp
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

    def test_masternode_can_receive_tx_and_send_to_other_nodes(self):
        self.network.create_new_network(
            num_of_masternodes=2,
            num_of_delegates=2
        )

        self.network.pause_all_queues()

        # wait for all publishers to register subscribers
        self.async_sleep(5)

        self.network.send_tx_to_random_masternode()

        self.async_sleep(5)

        for tn in self.network.all_nodes:
            self.assertEqual(1, len(tn.node.main_processing_queue))

    def test_node_network_can_propagate_transaction_results(self):
        self.network.create_new_network(
            num_of_masternodes=2,
            num_of_delegates=1
        )

        # wait for all publishers to register subscribers
        self.async_sleep(5)

        self.network.pause_all_validation_queues()

        self.network.send_tx_to_random_masternode()

        self.async_sleep(5)

        hlc_timestamp = self.network.masternodes[0].last_processed_hlc
        for tn in self.network.all_nodes:
            results = tn.node.validation_queue.get_validation_result(hlc_timestamp=hlc_timestamp)
            self.assertIsNotNone(results)
            solutions = results.get('solutions')
            print(solutions)
            self.assertEqual(3, len(list(solutions)))

    def test_node_network_can_mint_blocks(self):
        self.network.create_new_network(
            num_of_masternodes=2,
            num_of_delegates=1
        )

        # wait for all publishers to register subscribers
        self.async_sleep(5)

        self.network.send_tx_to_random_masternode()

        start_time = time.time()
        timeout = 120

        all_nodes_have_block = False
        while not all_nodes_have_block:
            all_nodes_have_block = True

            for tn in self.network.all_nodes:
                last_hlc_in_consensus = tn.node.validation_queue.last_hlc_in_consensus
                latest_block_number = nanos_from_hlc_timestamp(last_hlc_in_consensus)

                if latest_block_number <= 0:
                    all_nodes_have_block = False

            if time.time() - start_time > timeout:
                print("!!!! Timed out waiting for all nodes in network to mint blocks !!!!")
                break

        for tn in self.network.all_nodes:
            total_blocks = tn.node.blocks.total_blocks()
            self.assertEqual(2, total_blocks)











