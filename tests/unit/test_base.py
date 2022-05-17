from lamden import contracts
from lamden.crypto.wallet import Wallet
from lamden.nodes.base import Node
from tests.integration.mock.local_node_network import LocalNodeNetwork
from unittest import TestCase
import asyncio

class TestNode(TestCase):
    def setUp(self):
        self.local_node_network = LocalNodeNetwork(num_of_masternodes=1, genesis_path=contracts.__path__[0])
        self.node = self.local_node_network.masternodes[0]

    def tearDown(self):
        self.await_async_process(self.local_node_network.stop_all_nodes)

    def await_async_process(self, process, *args):
        task = asyncio.gather(
            process(*args)
        )
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(task)

    def test_node_type(self):
        self.assertEqual(self.node.node.node_type, 'masternode')

    def test_start_new_network_no_bootnodes(self):
        while not self.node.node_started:
            self.await_async_process(asyncio.sleep, 0.1)

        self.assertTrue(self.node.node_is_running)
        self.assertTrue(self.node.network.running)
        self.assertTrue(self.node.main_processing_queue.running)
        self.assertTrue(self.node.validation_queue.running)
        self.assertTrue(self.node.system_monitor.running)

    def test_start_new_network_bootnode_exists(self):
        new_node = self.local_node_network.add_masternode(should_seed=True)
        while not new_node.node_started:
            self.await_async_process(asyncio.sleep, 0.1)

        self.assertTrue(new_node.node_is_running)
        self.assertTrue(new_node.network.running)
        self.assertTrue(new_node.main_processing_queue.running)
        self.assertTrue(new_node.validation_queue.running)
        self.assertTrue(new_node.system_monitor.running)

    def test_start_join_existing_network_bootnode_exists(self):
        new_node = self.local_node_network.add_masternode()
        while not new_node.node_started:
            self.await_async_process(asyncio.sleep, 0.1)

        self.assertTrue(new_node.node_is_running)
        self.assertTrue(new_node.network.running)
        self.assertTrue(new_node.main_processing_queue.running)
        self.assertTrue(new_node.validation_queue.running)
        self.assertTrue(new_node.system_monitor.running)

    def test_start_join_existing_network_no_bootnodes(self):
        self.await_async_process(self.local_node_network.stop_all_nodes)

        wallet = Wallet()
        self.node = Node(socket_base='', wallet=wallet, constitution={}, should_seed=False)
        self.await_async_process(self.node.start)

        self.assertFalse(self.node.running)
        self.assertTrue(self.node.network.running)
        self.assertFalse(self.node.main_processing_queue.running)
        self.assertFalse(self.node.validation_queue.running)
        self.assertTrue(self.node.system_monitor.running)

        self.await_async_process(self.node.stop)

    def test_start_join_existing_network_bootnode_is_not_reachable(self):
        '''
            NOTE: lower number of 'attempts' inside Node.join_existing_network
            before running this one so it doesn't take forever to complete.
        '''
        self.await_async_process(self.local_node_network.stop_all_nodes)

        new_node = self.local_node_network.add_masternode()
        while new_node.node_is_running:
            self.await_async_process(asyncio.sleep, 0.1)

        # NOTE: wait for node to stop
        self.await_async_process(asyncio.sleep, 0.5)

        self.assertFalse(new_node.node_is_running)
        self.assertFalse(new_node.node_started)
        self.assertFalse(new_node.network.running)
        self.assertFalse(new_node.main_processing_queue.running)
        self.assertFalse(new_node.validation_queue.running)
        self.assertFalse(new_node.system_monitor.running)

        # TODO: assert revoked peer access; assert peer removed

    def test_stop(self):
        self.await_async_process(self.local_node_network.stop_all_nodes)

        self.assertFalse(self.node.node_is_running)
        self.assertFalse(self.node.network.running)
        self.assertFalse(self.node.main_processing_queue.running)
        self.assertFalse(self.node.validation_queue.running)
        self.assertFalse(self.node.system_monitor.running)
        self.assertFalse(self.node.node_started)

    def test_pause_all_queues(self):
        self.await_async_process(self.node.node.pause_all_queues)

        self.assertTrue(self.node.main_processing_queue.paused)
        self.assertTrue(self.node.validation_queue.paused)

        self.node.node.unpause_all_queues()

        self.assertFalse(self.node.main_processing_queue.paused)
        self.assertFalse(self.node.validation_queue.paused)

    def test_stop_main_processing_queue(self):
        self.await_async_process(self.node.node.stop_main_processing_queue)

        self.assertFalse(self.node.main_processing_queue.running)
        
import unittest
if __name__ == '__main__':
    unittest.main()
