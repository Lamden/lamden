'''
    !!!! THESE TESTS ARE LONG AND COULD EACH TAKE A FEW MINUTES TO COMPLETE !!!!

    THROUGHPUT Test send all transactions AT ONCE and then wait for all nodes to process them and come to consensus
    After all node are in sync then the test are run to validate state etc.

'''
from tests.integration.mock import mocks_new, create_directories
from lamden.crypto.wallet import Wallet

import zmq.asyncio
import asyncio

from unittest import TestCase


class TestMultiNode(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.n = None

    def tearDown(self):
        if self.n:
            self.await_async_process(self.n.stop)

        self.ctx.destroy()
        self.loop.close()

    def await_async_process(self, process):
        tasks = asyncio.gather(
            process()
        )
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)
        return res

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def send_transaction(self, node, tx):
        node.tx_queue.append(tx)

    def test_all_transactions_propegate_to_all_nodes(self):
        delay = {'base': 0.1, 'self': 0.2}
        self.n = mocks_new.MockNetwork(num_of_delegates=3, num_of_masternodes=3, ctx=self.ctx, metering=False, delay=delay)

        self.await_async_process(self.n.start)
        self.await_async_process(self.n.pause_all_queues)

        num_of_transactions_to_send = 100

        for i in range(num_of_transactions_to_send):
            self.n.send_random_currency_transaction(
                sender_wallet=Wallet()
            )

        self.async_sleep(25)

        for node in self.n.nodes:
            self.assertEqual(len(node.obj.main_processing_queue), num_of_transactions_to_send)

    def test_all_results_propegate_to_all_nodes(self):
        delay = {'base': 0.1, 'self': 0.2}
        self.n = mocks_new.MockNetwork(num_of_delegates=2, num_of_masternodes=3, ctx=self.ctx, metering=False, delay=delay)

        self.await_async_process(self.n.start)
        self.await_async_process(self.n.pause_all_validation_queues)

        num_of_transactions_to_send = 75

        for i in range(num_of_transactions_to_send):
            self.n.send_random_currency_transaction(
                sender_wallet=self.n.founder_wallet
            )

        self.async_sleep(25)

        for node in self.n.nodes:
            self.assertEqual(num_of_transactions_to_send, len(node.obj.validation_queue))
            for hlc_timestamp in node.obj.validation_queue.validation_results.keys():
                results = node.obj.validation_queue.validation_results.get(hlc_timestamp)
                solutions = results.get('solutions')
                self.assertEqual(len(self.n.nodes), len(solutions))

    def test_all_nodes_create_blocks_from_results(self):
        delay = {'base': 0.1, 'self': 0.2}
        self.n = mocks_new.MockNetwork(num_of_delegates=2, num_of_masternodes=3, ctx=self.ctx, metering=False,
                                       delay=delay)

        self.await_async_process(self.n.start)

        num_of_transactions_to_send = 55

        for i in range(num_of_transactions_to_send):
            self.n.send_random_currency_transaction(
                sender_wallet=Wallet()
            )

        self.async_sleep(25)

        # test all nodes have blocks ordered by hlc and the correct number of blocks
        for node in self.n.nodes:
            last_hlc = "0"
            for i in range(num_of_transactions_to_send):
                i = i + 1
                block = node.obj.get_block_by_number(block_number=i)
                self.assertIsNotNone(block)

                block_hlc_timestamp = block.get('hlc_timestamp')
                self.assertGreater(block_hlc_timestamp, last_hlc)

                last_hlc = block_hlc_timestamp