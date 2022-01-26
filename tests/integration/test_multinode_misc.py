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
            for node in self.n.nodes:
                if node.started:
                    self.await_async_process(node.obj.stop)

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
        delay = {'base': 1, 'self': 1.5}
        self.n = mocks_new.MockNetwork(num_of_delegates=2, num_of_masternodes=2, ctx=self.ctx, metering=False, delay=delay)

        self.await_async_process(self.n.start)
        self.await_async_process(self.n.pause_all_queues)

        num_of_transactions_to_send = 100

        for i in range(num_of_transactions_to_send):
            self.n.send_random_currency_transaction(
                sender_wallet=Wallet()
            )

        self.async_sleep(20)

        for node in self.n.nodes:
            self.assertEqual(len(node.obj.main_processing_queue), num_of_transactions_to_send)

    def test_all_results_propegate_to_all_nodes(self):
        delay = {'base': 1, 'self': 1.5}
        self.n = mocks_new.MockNetwork(num_of_delegates=2, num_of_masternodes=2, ctx=self.ctx, metering=False, delay=delay)

        self.await_async_process(self.n.start)
        self.await_async_process(self.n.pause_all_queues)

        num_of_transactions_to_send = 25

        for i in range(num_of_transactions_to_send):
            self.n.send_random_currency_transaction(
                sender_wallet=self.n.founder_wallet
            )

        self.async_sleep(10)

        for node in self.n.nodes:
            self.assertEqual(num_of_transactions_to_send, len(node.obj.main_processing_queue))

        self.n.unpause_all_main_processing_queues()

        self.async_sleep(10)

        for node in self.n.nodes:
            self.assertEqual(num_of_transactions_to_send, len(node.obj.validation_queue))
            for hlc_timestamp in node.obj.validation_queue.validation_results.keys():
                results = node.obj.validation_queue.validation_results.get(hlc_timestamp)
                solutions = results.get('solutions')
                self.assertEqual(len(self.n.nodes), len(solutions))



    def test_all_nodes_create_blocks_from_results(self):
        delay = {'base': 1, 'self': 1.5}
        self.n = mocks_new.MockNetwork(num_of_delegates=1, num_of_masternodes=1, ctx=self.ctx, metering=False,
                                       delay=delay)

        self.await_async_process(self.n.start)
        self.await_async_process(self.n.pause_all_queues)

        num_of_transactions_to_send = 5

        for i in range(num_of_transactions_to_send):
            self.n.send_random_currency_transaction(
                sender_wallet=Wallet()
            )

        self.async_sleep(5)

        for node in self.n.nodes:
            self.assertEqual(num_of_transactions_to_send, len(node.obj.main_processing_queue))

        self.n.unpause_all_main_processing_queues()

        self.async_sleep(5)

        lastest_hlc = "0"

        for node in self.n.nodes:
            self.assertEqual(num_of_transactions_to_send, len(node.obj.validation_queue))
            for hlc_timestamp in node.obj.validation_queue.validation_results.keys():
                if hlc_timestamp > lastest_hlc:
                    lastest_hlc = hlc_timestamp
                results = node.obj.validation_queue.validation_results.get(hlc_timestamp)
                solutions = results.get('solutions')
                self.assertEqual(len(self.n.nodes), len(solutions))

        self.n.unpause_all_validation_queues()

        self.async_sleep(10)

        for node in self.n.nodes:
            block = node.obj.get_block_by_hlc(hlc_timestamp=lastest_hlc)
            self.assertEqual(num_of_transactions_to_send, block['number'])