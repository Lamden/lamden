from lamden import contracts
from lamden.crypto.wallet import Wallet
from lamden.nodes.base import Node, ensure_in_constitution
from lamden.nodes.hlc import HLC_Clock
from tests.integration.mock.local_node_network import LocalNodeNetwork
from tests.unit.helpers.mock_transactions import get_new_currency_tx
from unittest import TestCase
import asyncio
import json

import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

class TestMisc(TestCase):
    def test_ensure_in_constitution_raises_if_not_in_constitution(self):
        constitution = {'masternodes': {Wallet().verifying_key: "127.0.0.1"},
            'delegates': {Wallet().verifying_key: "127.0.0.1"}}

        with self.assertRaises(AssertionError):
            ensure_in_constitution(Wallet().verifying_key, constitution=constitution)

    def test_ensure_in_constitution_doesnt_raises_if_in_constitution(self):
        vk = Wallet().verifying_key
        constitution = {'masternodes': {vk: "127.0.0.1"},
            'delegates': {Wallet().verifying_key: "127.0.0.1"}}

        ensure_in_constitution(vk, constitution=constitution)

class TestNode(TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.local_node_network = LocalNodeNetwork(num_of_masternodes=1, genesis_path=contracts.__path__[0])
        self.node = self.local_node_network.masternodes[0]

    def tearDown(self):
        if self.local_node_network:
            for tn in self.local_node_network.all_nodes:
                loop = asyncio.get_event_loop()
                loop.run_until_complete(tn.stop())

            for tn in self.local_node_network.all_nodes:
                tn.join()

        self.loop.stop()
        self.loop.close()


    def await_async_process(self, process, *args, **kwargs):
        task = asyncio.gather(
            process(*args, **kwargs)
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

        # NOTE: wait for node to stop
        self.await_async_process(asyncio.sleep, 0.5)

        self.assertFalse(self.node.running)
        self.assertFalse(self.node.network.running)
        self.assertFalse(self.node.main_processing_queue.running)
        self.assertFalse(self.node.validation_queue.running)
        self.assertFalse(self.node.system_monitor.running)

        self.await_async_process(self.node.stop)

    def test_start_join_existing_network_bootnode_is_not_reachable(self):
        self.await_async_process(self.local_node_network.stop_all_nodes)

        new_node = self.local_node_network.add_masternode(reconnect_attempts=1)
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

    def test_force_stop_main_processing_queue(self):
        self.await_async_process(self.node.node.stop_main_processing_queue, force=True)

        self.assertFalse(self.node.main_processing_queue.currently_processing)


    def test_start_main_processing_queue(self):
        self.node.node.start_main_processing_queue()

        self.assertTrue(self.node.main_processing_queue.running)

    def test_pause_tx_queue(self):
        self.node.node.pause_tx_queue()

        self.assertTrue(self.node.node.pause_tx_queue_checking)
    
    def test_unpause_tx_queue(self):
        self.node.node.unpause_tx_queue()

        self.assertFalse(self.node.node.pause_tx_queue_checking)

    def test_check_tx_queue_triggers_block_creation(self):
        self.node.contract_driver.set_var(contract='currency', variable='balances', arguments=[self.node.wallet.verifying_key], value=1000)

        self.assertIsNone(self.node.node.blocks.get_block(1))

        tx = json.dumps(get_new_currency_tx(wallet=self.node.wallet))
        self.node.send_tx(tx.encode())

        self.await_async_process(asyncio.sleep, 2)

        self.assertEqual(len(self.node.node.tx_queue), 0)
        self.assertIsNotNone(self.node.node.blocks.get_block(1))

    def test_process_tx_when_later_blocks_exist_inserts_block_inorder(self):
        self.node.contract_driver.set_var(contract='currency', variable='balances', arguments=[self.node.wallet.verifying_key], value=1000)

        for i in range(3):
            tx = json.dumps(get_new_currency_tx(wallet=self.node.wallet))
            self.node.send_tx(tx.encode())

        self.await_async_process(asyncio.sleep, 3)

        old_tx = get_new_currency_tx(wallet=self.node.wallet)
        old_tx = self.node.node.make_tx_message(old_tx)

        self.await_async_process(asyncio.sleep, 2)

        for i in range(3):
            tx = json.dumps(get_new_currency_tx(wallet=self.node.wallet))
            self.node.send_tx(tx.encode())

        self.await_async_process(asyncio.sleep, 3)

        self.node.node.main_processing_queue.append(old_tx)

        self.await_async_process(asyncio.sleep, 2)

        self.assertEqual(len(self.node.node.tx_queue), 0)
        self.assertEqual(self.node.node.blocks.get_block(4)['hlc_timestamp'], old_tx['hlc_timestamp'])

    def test_make_tx_message(self):
        tx = get_new_currency_tx(wallet=self.node.wallet)

        tx_message = self.node.node.make_tx_message(tx)

        self.assertIsNotNone(tx_message.get('tx', None))
        self.assertIsNotNone(tx_message.get('hlc_timestamp', None))
        self.assertIsNotNone(tx_message.get('signature', None))
        self.assertIsNotNone(tx_message.get('sender', None))

    def test_process_main_queue_sets_last_processed_hlc(self):
        self.node.contract_driver.set_var(contract='currency', variable='balances', arguments=[self.node.wallet.verifying_key], value=1000)
        tx = get_new_currency_tx(wallet=self.node.wallet)
        tx = self.node.node.make_tx_message(tx)

        self.node.node.main_processing_queue.append(tx)

        self.await_async_process(asyncio.sleep, 2)

        self.assertEqual(self.node.node.last_processed_hlc, tx['hlc_timestamp'])

    def test_process_main_queue_doesnt_set_last_processed_hlc_if_later_than_last_hlc_in_consensus(self):
        self.node.contract_driver.set_var(contract='currency', variable='balances', arguments=[self.node.wallet.verifying_key], value=1000)
        tx = get_new_currency_tx(wallet=self.node.wallet)
        tx = self.node.node.make_tx_message(tx)
        self.node.validation_queue.last_hlc_in_consensus = tx['hlc_timestamp']

        self.node.node.main_processing_queue.append(tx)

        self.await_async_process(asyncio.sleep, 2)

        self.assertNotEqual(self.node.node.last_processed_hlc, tx['hlc_timestamp'])

    def test_store_solution_and_send_to_network(self):
        hlc = HLC_Clock().get_new_hlc_timestamp()
        processing_results = {'hlc_timestamp': hlc, 'tx_result': {}, 'proof' : {}}

        self.node.node.store_solution_and_send_to_network(processing_results)

        self.assertIn(hlc, self.node.validation_queue.append_history)
        self.assertIsNotNone(processing_results['proof'].get('tx_result_hash', None))

    def test_update_block_db(self):
        block = {'hash': 'sample_hash', 'number': 1}
        self.node.node.update_block_db(block)

        self.assertEqual(self.node.node.get_current_hash(), 'sample_hash')
        self.assertEqual(self.node.node.get_current_height(), 1)

    def test_get_state_changes_from_block(self):
        block = {'processed': {'state': 'sample_state'}}

        self.assertEqual(self.node.node.get_state_changes_from_block(block), 'sample_state')

    def test_soft_apply_current_state(self):
        hlc = HLC_Clock().get_new_hlc_timestamp()
        self.node.node.driver.set('key', 'sample_value')

        self.node.node.soft_apply_current_state(hlc)

        self.assertDictEqual(self.node.node.driver.pending_deltas[hlc],
            {'writes': {'key': (None, 'sample_value')}, 'reads': {'key': None}})

    def test_apply_state_changes_from_block(self):
        block = {'hlc_timestamp': HLC_Clock().get_new_hlc_timestamp(),
            'processed': {'state': [{'key': 'key', 'value': 'sample_value'}]}}

        self.node.node.apply_state_changes_from_block(block)

        self.assertEqual(self.node.node.driver.driver.get('key'), 'sample_value')

import unittest
if __name__ == '__main__':
    unittest.main()
