from contracting.db.driver import ContractDriver, FSDriver
from lamden.crypto.wallet import Wallet
from lamden.nodes.base import Node
from lamden.nodes.events import EventWriter
from lamden.nodes.hlc import HLC_Clock
from pathlib import Path
from tests.integration.mock.local_node_network import LocalNodeNetwork
from tests.unit.helpers.mock_transactions import get_new_currency_tx, get_processing_results
from unittest import TestCase
import asyncio
import json
import shutil
import uvloop
import time

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

class TestNode(TestCase):
    def setUp(self):
        self.local_node_network = LocalNodeNetwork(num_of_masternodes=1)
        self.node = self.local_node_network.masternodes[0]

        self.loop = asyncio.get_event_loop()

        while not self.node.node.started or not self.node.network.is_running:
            self.loop.run_until_complete(asyncio.sleep(1))

    def tearDown(self):
        self.await_async_process(self.local_node_network.stop_all_nodes)

    def await_async_process(self, process, *args, **kwargs):
        task = asyncio.gather(
            process(*args, **kwargs)
        )
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(task)

    def test_start_new_network_no_bootnodes(self):
        while not self.node.node_started:
            self.await_async_process(asyncio.sleep, 0.1)

        self.assertTrue(self.node.node_is_running)
        self.assertTrue(self.node.network.running)
        self.assertTrue(self.node.main_processing_queue.running)
        self.assertTrue(self.node.validation_queue.running)
        self.assertTrue(self.node.system_monitor.running)

    def test_start_new_network_bootnode_exists(self):
        new_node = self.local_node_network.add_masternode()
        while not new_node.node_started:
            self.await_async_process(asyncio.sleep, 0.1)

        self.assertTrue(new_node.node_is_running)
        self.assertTrue(new_node.network.running)
        self.assertTrue(new_node.main_processing_queue.running)
        self.assertTrue(new_node.validation_queue.running)
        self.assertTrue(new_node.system_monitor.running)

    def test_start_join_existing_network_bootnode_exists(self):
        new_node = self.local_node_network.join_masternode()
        while not new_node.node_started:
            self.await_async_process(asyncio.sleep, 0.1)

        self.assertTrue(new_node.node_is_running)
        self.assertTrue(new_node.network.running)
        self.assertTrue(new_node.main_processing_queue.running)
        self.assertTrue(new_node.validation_queue.running)
        self.assertTrue(new_node.system_monitor.running)

    def test_start_join_existing_network_no_bootnodes(self):
        self.await_async_process(self.local_node_network.stop_all_nodes)

        path = Path().cwd().joinpath("temp_storage")
        self.node = Node(wallet=Wallet(), join=True, driver=ContractDriver(driver=FSDriver(root=path)), event_writer=EventWriter(root=path))
        self.await_async_process(self.node.start)

        self.assertFalse(self.node.running)
        self.assertFalse(self.node.network.running)
        self.assertFalse(self.node.main_processing_queue.running)
        self.assertFalse(self.node.validation_queue.running)
        self.assertFalse(self.node.system_monitor.running)

        shutil.rmtree(path)

    def test_start_join_existing_network_bootnode_is_not_reachable(self):
        self.await_async_process(self.local_node_network.stop_all_nodes)

        new_node = self.local_node_network.join_masternode(reconnect_attempts=1)

        while new_node.node_is_running:
            self.await_async_process(asyncio.sleep, 0.1)

        # NOTE: wait for node to stop
        self.await_async_process(asyncio.sleep, 3)

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

    def test_METHOD_cancel_checking_all_queues__waits_for_all_checking_tasks_to_be_done(self):
        loop = asyncio.get_event_loop()

        loop.run_until_complete(self.node.node.cancel_checking_all_queues())

        self.assertTrue(self.node.node.check_main_processing_queue_task.done())
        self.assertTrue(self.node.node.check_validation_queue_task.done())

    def test_METHOD_pause_main_processing_queue(self):
        self.await_async_process(self.node.node.pause_main_processing_queue)
        self.assertTrue(self.node.main_processing_queue.paused)

    def test_METHOD_pause_validation_queue(self):
        self.await_async_process(self.node.node.pause_validation_queue)
        self.assertTrue(self.node.validation_queue.paused)

    def test_pause_all_queues(self):
        self.await_async_process(self.node.node.pause_all_queues)

        self.assertTrue(self.node.main_processing_queue.paused)
        self.assertTrue(self.node.validation_queue.paused)
    '''
    def test_pause_tx_queue(self):
        self.node.node.pause_tx_queue()

        self.await_async_process(asyncio.sleep(1))
        self.assertTrue(self.node.node.pause_tx_queue_checking)
    
    def test_unpause_tx_queue(self):
        self.node.node.unpause_tx_queue()
        self.await_async_process(asyncio.sleep(1))
        self.assertFalse(self.node.node.pause_tx_queue_checking)
    '''

    def test_check_tx_queue_triggers_block_creation(self):
        self.node.contract_driver.set_var(contract='currency', variable='balances', arguments=[self.node.wallet.verifying_key], value=1000)

        self.assertEqual(1, self.node.blocks.total_blocks())

        tx = json.dumps(get_new_currency_tx(wallet=self.node.wallet, processor=self.node.vk))
        self.node.send_tx(tx.encode())

        self.await_async_process(asyncio.sleep, 8)

        self.assertEqual(len(self.node.node.tx_queue), 0)
        last_hlc_timestamp = self.node.validation_queue.last_hlc_in_consensus
        self.assertIsNotNone(self.node.node.blocks.get_block(last_hlc_timestamp))




    ''' N/A
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
    '''

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

        self.assertEqual(self.node.node.get_last_processed_hlc(), tx['hlc_timestamp'])

    def test_process_main_queue_doesnt_set_last_processed_hlc_if_later_than_last_hlc_in_consensus(self):
        self.node.contract_driver.set_var(contract='currency', variable='balances', arguments=[self.node.wallet.verifying_key], value=1000)
        tx = get_new_currency_tx(wallet=self.node.wallet)
        tx = self.node.node.make_tx_message(tx)
        self.node.validation_queue.last_hlc_in_consensus = tx['hlc_timestamp']

        self.node.node.main_processing_queue.append(tx)

        self.await_async_process(asyncio.sleep, 2)

        self.assertNotEqual(self.node.node.get_last_processed_hlc(), tx['hlc_timestamp'])

    def test_store_solution_and_send_to_network(self):
        hlc = HLC_Clock().get_new_hlc_timestamp()
        processing_results = {'hlc_timestamp': hlc, 'tx_result': {}, 'proof' : {'tx_result_hash':"123"}, 'rewards': []}

        self.await_async_process(self.node.node.pause_validation_queue)
        self.node.node.store_solution_and_send_to_network(processing_results)

        self.assertIn(hlc, self.node.validation_queue.append_history)

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

        self.assertEqual('sample_value', self.node.node.driver.driver.get('key'))

    def test_processing_transactions_does_not_drop_state(self):
        num_of_transactions = 1000

        processing_delay_secs = {
            'base': 0,
            'self': 0
        }

        self.node.node.processing_delay_secs = processing_delay_secs
        self.node.node.driver.driver.set(f'currency.balances:{self.node.wallet.verifying_key}', 10000000)

        loop = asyncio.get_event_loop()

        loop.run_until_complete(self.node.node.cancel_checking_all_queues())

        for i in range(num_of_transactions):
            currency_tx = get_new_currency_tx(wallet=self.node.wallet)
            tx = self.node.node.make_tx_message(tx=currency_tx)

            self.node.main_processing_queue.append(tx=tx)
            processing_results = loop.run_until_complete(self.node.node.main_processing_queue.process_next())
            tx_result = processing_results.get('tx_result')
            self.assertGreater(len(tx_result['state']), 0)
            self.node.node.soft_apply_current_state(processing_results.get('hlc_timestamp'))

    def test_check_peers_stops_self_if_kicked_out(self):
        self.node.set_smart_contract_value('masternodes.S:members', [])
        processing_results = {
            'tx_result': {
                'state': [
                    {'key': 'masternodes.S:members', 'value': []}
                ]
            }
        }

        self.node.node.check_peers(
            state_changes=processing_results['tx_result'].get('state'),
            hlc_timestamp=processing_results.get('hlc_timestamap')
        )

        self.await_async_process(asyncio.sleep, 3)

        self.assertFalse(self.node.node_is_running)
        self.assertFalse(self.node.network.running)
        self.assertFalse(self.node.main_processing_queue.running)
        self.assertFalse(self.node.validation_queue.running)
        self.assertFalse(self.node.system_monitor.running)

    def test_check_peers_stops_peer_if_kicked_out(self):
        other_node = self.local_node_network.join_masternode()

        self.await_async_process(asyncio.sleep, 1)
        self.assertEqual(self.node.network.num_of_peers(), 1)

        while not self.await_async_process(other_node.network.connected_to_all_peers):
            self.await_async_process(asyncio.sleep, 1)

        while not self.await_async_process(self.node.network.connected_to_all_peers):
            self.await_async_process(asyncio.sleep, 1)


        self.node.set_smart_contract_value('masternodes.S:members', [self.node.wallet.verifying_key])
        other_node.set_smart_contract_value('masternodes.S:members', [self.node.wallet.verifying_key])
        processing_results = {
            'tx_result': {
                'state': [
                    {'key': 'masternodes.S:members', 'value': [f'{self.node.wallet.verifying_key}']}
                ]
            }
        }

        self.node.node.check_peers(
            state_changes=processing_results['tx_result'].get('state'),
            hlc_timestamp=processing_results.get('hlc_timestamap')
        )

        other_node.node.check_peers(
            state_changes=processing_results['tx_result'].get('state'),
            hlc_timestamp=processing_results.get('hlc_timestamap')
        )

        self.await_async_process(asyncio.sleep, 5)

        # node
        self.assertEqual(self.node.network.num_of_peers(), 0)
        self.assertTrue(self.node.node_is_running)
        self.assertTrue(self.node.network.running)
        self.assertTrue(self.node.main_processing_queue.running)
        self.assertTrue(self.node.validation_queue.running)
        self.assertTrue(self.node.system_monitor.running)

        started_check = time.time()
        while other_node.node_is_running:
            self.assertLess(time.time() - started_check, 10, msg="Hit timeout waiting for network to start.")
            self.await_async_process(asyncio.sleep, 0.5)

        # other_node
        self.assertFalse(other_node.node_is_running)
        self.assertFalse(other_node.network.running)
        print("[TEST CASE] Checking self.node.main_processing_queue.running")
        self.assertFalse(other_node.main_processing_queue.running)
        self.assertFalse(other_node.validation_queue.running)
        self.assertFalse(other_node.system_monitor.running)

    def test_check_peers_removes_results_which_belong_to_exiled_node(self):
        peer_wallet = Wallet()
        peer_vk = peer_wallet.verifying_key
        self.node.set_smart_contract_value('masternodes.S:members', [self.node.wallet.verifying_key, peer_vk])
        self.node.network.connect_peer(ip='tcp://127.0.0.1:19001', vk=peer_vk)
        self.assertEqual(self.node.network.num_of_peers(), 1)

        self.await_async_process(self.node.node.cancel_checking_all_queues)

        processing_results = get_processing_results(
            tx_message=self.node.node.make_tx_message(tx=get_new_currency_tx(wallet=self.node.wallet)),
            node_wallet=peer_wallet,
            driver=self.node.contract_driver
        )
        older_hlc = processing_results['hlc_timestamp']

        self.node.validation_queue.append(processing_results)

        self.assertIsNotNone(self.node.validation_queue.validation_results[older_hlc]['solutions'].get(peer_vk, None))
        self.assertIsNotNone(self.node.validation_queue.validation_results[older_hlc]['proofs'].get(peer_vk, None))

        processing_results = {
            'hlc_timestamp': '0', # NOTE: earlier HLC than we already have in validation queue
            'tx_result': {
                'state': [
                    {'key': 'masternodes.S:members', 'value': [f'{self.node.wallet.verifying_key}']}
                ]
            }
        }
        self.node.set_smart_contract_value('masternodes.S:members', [self.node.wallet.verifying_key])
        self.node.node.check_peers(
            state_changes=processing_results['tx_result'].get('state'),
            hlc_timestamp=processing_results.get('hlc_timestamap')
        )

        self.assertIsNone(self.node.validation_queue.validation_results[older_hlc]['solutions'].get(peer_vk, None))
        self.assertIsNone(self.node.validation_queue.validation_results[older_hlc]['proofs'].get(peer_vk, None))

import unittest
if __name__ == '__main__':
    unittest.main()
