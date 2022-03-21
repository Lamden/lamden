from tests.integration.mock.mocks_multip import TEST_FOUNDATION_WALLET,  MockNetwork, create_fixture_directories, remove_fixture_directories
from lamden.nodes.hlc import HLC_Clock

import zmq.asyncio
import asyncio
from unittest import TestCase
from sys import setrecursionlimit

setrecursionlimit(20000)


class TestMultiNode(TestCase):
    def setUp(self):
        self.fixture_directories = ['block_storage', 'file_queue', 'nonces', 'pending-nonces']
        # remove_fixture_directories(self.fixture_directories)
        create_fixture_directories(self.fixture_directories)

        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.network = None
        self.hlc_clock = HLC_Clock()

        self.founder_wallet = TEST_FOUNDATION_WALLET
        print("\n")

    def tearDown(self):
        for node_process in self.network.all_nodes():
            try:
                node_process.process.terminate()
            except Exception:
                pass

        self.ctx.destroy()
        self.loop.close()

        remove_fixture_directories(self.fixture_directories)

    def await_async_process(self, process, args={}):
        tasks = asyncio.gather(
            process(**args)
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

    def test_network_starts_and_stops(self):
        self.network = MockNetwork(num_of_masternodes=5, num_of_delegates=5)
        self.await_async_process(self.network.start)
        self.await_async_process(self.network.await_all_started)

        for node_process in self.network.masternodes:
            self.assertTrue(node_process.started)

        self.async_sleep(20)

        self.await_async_process(self.network.stop)

        for node_process in self.network.masternodes:
            self.assertFalse(node_process.started)

    def test_await_all_started(self):
        self.network = MockNetwork(num_of_masternodes=5, num_of_delegates=5)
        self.await_async_process(self.network.start)
        self.await_async_process(self.network.await_all_started)

        for node_process in self.network.all_nodes():
            self.assertTrue(node_process.started)

    def test_await_get_all_node_types(self):
        self.network = MockNetwork(num_of_masternodes=5, num_of_delegates=5)
        self.await_async_process(self.network.start)
        self.await_async_process(self.network.await_all_started)
        self.await_async_process(self.network.await_get_all_node_types)

        for node_process in self.network.masternodes:
            self.assertEqual('masternode', node_process.node_type)

        for node_process in self.network.delegates:
            self.assertEqual('delegate', node_process.node_type)

    def test_append_tx_to_node_tx_queue(self):
        # Create a network
        self.network = MockNetwork(num_of_masternodes=1, num_of_delegates=1)
        self.await_async_process(self.network.start)
        self.await_async_process(self.network.await_all_started)

        # Get a maternode process
        node_process = self.network.masternodes[0]

        # Send a TX to the Node
        self.network.send_currency_transaction(node_process=node_process, sender_wallet=self.founder_wallet)

        self.await_async_process(node_process.await_get_file_queue_length)[0]

        while node_process.file_queue_length is 1:
            self.await_async_process(node_process.await_get_file_queue_length)[0]

        print('queue_length"', node_process.file_queue_length)


        '''
        # Wait till the node processes the transaction
        node_new_hlc = node_current_hlc
        while node_current_hlc == node_new_hlc:
            node_new_hlc = self.await_async_process(node_process.get_last_processed_hlc)[0]

        self.assertGreater(node_new_hlc, node_current_hlc)
        '''

    def test_send_transaction_to_network(self):
        # Create a network
        self.network = MockNetwork(num_of_masternodes=1, num_of_delegates=0)
        self.await_async_process(self.network.start)
        self.await_async_process(self.network.await_all_started)

        # Get a maternode process
        node_process = self.network.masternodes[0]
        node_process.last_processed_hlc = None

        # Get the nodes current HLC
        node_current_hlc = self.await_async_process(node_process.state.metadata.get_last_processed_hlc)[0]

        # Send a TX to the Node
        self.network.send_currency_transaction(node_process=node_process)

        while node_process.file_queue_length is None:
            queue_length = self.await_async_process(node_process.await_get_file_queue_length)[0]
            pass
        '''
        # Wait till the node processes the transaction
        node_new_hlc = node_current_hlc
        while node_current_hlc == node_new_hlc:
            node_new_hlc = self.await_async_process(node_process.get_last_processed_hlc)[0]

        self.assertGreater(node_new_hlc, node_current_hlc)
        '''


