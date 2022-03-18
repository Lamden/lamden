from lamden.nodes.masternode import masternode
from lamden.nodes import base
from lamden import storage
from lamden.crypto.wallet import Wallet
from lamden.crypto.canonical import tx_result_hash_from_tx_result_object
from contracting.db.driver import InMemDriver, ContractDriver
from contracting.client import ContractingClient
from contracting.db import encoder
from contracting.db.driver import encode
from contracting.stdlib.bridge.decimal import ContractingDecimal
import zmq.asyncio
import asyncio

from lamden.nodes.processing_queue import make_tx_message
from tests.unit.helpers.mock_transactions import get_new_currency_tx, get_tx_message, get_processing_results

from unittest import TestCase

class TestNode(TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.num_of_nodes = 0

        self.blocks = storage.BlockStorage()

        self.driver = ContractDriver(driver=InMemDriver())

        self.stu_wallet = Wallet()
        self.jeff_wallet = Wallet()
        self.archer_wallet = Wallet()
        self.oliver_wallet = Wallet()

        self.b = masternode.BlockService(
            blocks=self.blocks,
            driver=self.driver
        )

        self.blocks.flush()
        self.driver.flush()

        self.node = None
        self.nodes = []

        print("\n")

    def tearDown(self):
        for node in self.nodes:
            if node.running:
                self.stop_node(node=node)

        self.loop.close()
        self.b.blocks.flush()
        self.b.driver.flush()

    def create_a_node(self, constitution=None, bootnodes = None, node_num=0):
        driver = ContractDriver(driver=InMemDriver())

        dl_wallet = Wallet()
        mn_wallet = Wallet()

        constitution = constitution or {
                'masternodes': [mn_wallet.verifying_key],
                'delegates': [dl_wallet.verifying_key]
            }

        if bootnodes is None:
            bootnodes = {}
            bootnodes[mn_wallet.verifying_key] = f'tcp://127.0.0.1:19000'
            bootnodes[dl_wallet.verifying_key] = f'tcp://127.0.0.1:19001'

        node = base.Node(
            socket_base=f'tcp://127.0.0.1:{19000 + node_num}',
            wallet=mn_wallet,
            constitution=constitution,
            bootnodes=bootnodes,
            driver=driver,
            testing=True,
            metering=False,
            delay={
                'base': 0,
                'self': 0
            }
        )

        node.network.socket_ports['router'] = 19000 + node_num
        node.network.socket_ports['webserver'] = 18080 + node_num
        node.network.socket_ports['publisher'] = 19080 + node_num

        node.client.set_var(
            contract='currency',
            variable='balances',
            arguments=[self.stu_wallet.verifying_key],
            value=1_000_000
        )

        node.driver.commit()

        self.num_of_nodes = self.num_of_nodes + 1

        self.nodes.append(node)

        if node_num > 0:
            return node
        else:
            self.node = node

    def start_node(self, node=None):
        if (node):
            print("other node")
            self.await_async_process(node.start)
        else:
            print("self node")
            self.await_async_process(self.node.start)

    def start_all_nodes(self):
        for node in self.nodes:
            self.await_async_process(node.start)

    def stop_node(self, node=None):
        if (node):
            self.await_async_process(node.stop)
        else:
            self.await_async_process(self.node.stop)

    def await_async_process(self, process):
        tasks = asyncio.gather(
            process()
        )
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)
        return res

    def await_hard_apply_block(self, node, processing_results):
        tasks = asyncio.gather(
            node.hard_apply_block(processing_results=processing_results)
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

    async def delay_processing_await(self, func, delay):
        await asyncio.sleep(delay)
        if func:
            return await func()

    def await_async_process_next(self, node):
        tasks = asyncio.gather(
            self.delay_processing_await(node.main_processing_queue.process_next, 0.1),
        )
        loop = asyncio.get_event_loop()
        res =  loop.run_until_complete(tasks)
        print(res)
        return res[0]

    def process_a_tx(self, node, tx_message):
        processing_results = get_processing_results(node=node, tx_message=tx_message)
        hlc_timestamp = processing_results.get('hlc_timestamp')

        node.last_processed_hlc = hlc_timestamp
        node.soft_apply_current_state(hlc_timestamp=hlc_timestamp)

        node.store_solution_and_send_to_network(processing_results=processing_results)

        self.async_sleep(0.01)

        return processing_results

    def test_reprocessing_should_reprocess_all_has_both(self):
        # This will test where all transactions share keys
        # TX #2 and #3 would have created state but will have different state after #1 is reprocessed
        self.create_a_node()
        self.start_all_nodes()

        # stop the validation queue
        self.node.validation_queue.pause()

        stu_balance_before = self.node.driver.driver.get(f'currency.balances:{self.stu_wallet.verifying_key}')

        tx_amount = 200.1
        tx_args = {
            'to': self.jeff_wallet.verifying_key,
            'wallet': self.stu_wallet,
            'amount': tx_amount
        }

        tx_message_1 = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(**tx_args))
        hlc_timestamp_1 = tx_message_1['hlc_timestamp']
        tx_message_2 = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(**tx_args))
        hlc_timestamp_2 = tx_message_2['hlc_timestamp']
        tx_message_3 = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(**tx_args))
        hlc_timestamp_3 = tx_message_3['hlc_timestamp']

        # add this tx the processing queue so we can process it
        self.node.main_processing_queue.append(tx=tx_message_2)
        self.node.main_processing_queue.append(tx=tx_message_3)

        self.async_sleep(0.1)

        self.node.main_processing_queue.append(tx=tx_message_1)

        self.async_sleep(0.1)

        self.node.driver.hard_apply(hlc=hlc_timestamp_3)

        stu_balance_after = self.node.driver.driver.get(f'currency.balances:{self.stu_wallet.verifying_key}')

        stu_balance_delta = stu_balance_before - stu_balance_after

        self.assertEqual(str(tx_amount * 3), str(stu_balance_delta))

        debug_reprocessing_results = self.node.debug_reprocessing_results
        self.assertEqual('has_both', debug_reprocessing_results[hlc_timestamp_2]['reprocess_type'])
        self.assertTrue(debug_reprocessing_results[hlc_timestamp_2]['sent_to_network'])
        self.assertEqual('has_both', debug_reprocessing_results[hlc_timestamp_3]['reprocess_type'])
        self.assertTrue(debug_reprocessing_results[hlc_timestamp_3]['sent_to_network'])

    def test_reprocessing_should_reprocess_all_no_deltas(self):
        # This will test where TX #2 and #3 would fail due to no balance to send
        # TX #1 is the late tx and after reprocessing it will supply the balance for #2 and #3 to be successful

        self.create_a_node()
        self.start_all_nodes()

        # stop the validation queue
        self.node.validation_queue.stop()

        # Set the HLC of the last consensus
        self.node.validation_queue.last_hlc_in_consensus = "0"
        self.node.last_processed_hlc = "0"

        stu_balance_before = self.node.driver.driver.get(f'currency.balances:{self.stu_wallet.verifying_key}')

        tx_amount = 200.1
        # Send from Stu to Jeff
        tx_message_1 = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(
            to=self.jeff_wallet.verifying_key,
            wallet=self.stu_wallet,
            amount=tx_amount
        ))

        # Send from Jeff to Archer
        tx_message_2 = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(
            to=self.archer_wallet.verifying_key,
            wallet=self.jeff_wallet,
            amount=tx_amount
        ))
        hlc_timestamp_2 = tx_message_2['hlc_timestamp']
        # Send from Archer to Jeff
        tx_message_3 = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(
            to=self.jeff_wallet.verifying_key,
            wallet=self.archer_wallet,
            amount=tx_amount
        ))
        hlc_timestamp_3 = tx_message_3['hlc_timestamp']

        # add this tx the processing queue so we can process it
        self.node.main_processing_queue.append(tx=tx_message_2)
        self.node.main_processing_queue.append(tx=tx_message_3)

        self.async_sleep(0.1)

        self.node.main_processing_queue.append(tx=tx_message_1)

        self.async_sleep(0.1)

        self.node.driver.hard_apply(hlc=hlc_timestamp_3)

        stu_balance_after = self.node.driver.driver.get(f'currency.balances:{self.stu_wallet.verifying_key}')
        jeff_balance_after = self.node.driver.driver.get(f'currency.balances:{self.jeff_wallet.verifying_key}')
        archer_balance_after = self.node.driver.driver.get(f'currency.balances:{self.archer_wallet.verifying_key}')

        self.assertEqual(tx_amount, stu_balance_before - stu_balance_after)
        self.assertEqual(tx_amount, jeff_balance_after)
        self.assertEqual(0, archer_balance_after)

        debug_reprocessing_results = self.node.debug_reprocessing_results
        self.assertEqual('no_deltas', debug_reprocessing_results[hlc_timestamp_2]['reprocess_type'])
        self.assertTrue(debug_reprocessing_results[hlc_timestamp_2]['sent_to_network'])
        self.assertEqual('no_deltas', debug_reprocessing_results[hlc_timestamp_3]['reprocess_type'])
        self.assertTrue(debug_reprocessing_results[hlc_timestamp_3]['sent_to_network'])


    def test_reprocessing_should_reprocess_all_no_writes(self):
        # This will test where TX #3 will initially have pending deltas because TX #1 gave it a balance
        # TX #2 will be late late tx and after reprocessing TX #2 will not have the balance to send (no deltas) as TX #3
        # will have spent it

        self.create_a_node()
        self.start_all_nodes()

        # stop the validation queue
        self.node.validation_queue.stop()

        # Set the HLC of the last consensus
        self.node.validation_queue.last_hlc_in_consensus = "0"
        self.node.last_processed_hlc = "0"

        stu_balance_before = self.node.driver.driver.get(f'currency.balances:{self.stu_wallet.verifying_key}')

        tx_amount = 200.1
        # Send from Stu to Jeff
        tx_message_1 = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(
            wallet=self.stu_wallet,
            to=self.jeff_wallet.verifying_key,
            amount=tx_amount
        ))

        # Send from Jeff to Archer
        tx_message_2 = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(
            wallet=self.jeff_wallet,
            to=self.archer_wallet.verifying_key,
            amount=tx_amount
        ))

        # Send from Jeff to Archer
        tx_message_3 = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(
            wallet=self.jeff_wallet,
            to=self.archer_wallet.verifying_key,
            amount=tx_amount
        ))
        hlc_timestamp_3 = tx_message_3['hlc_timestamp']

        # add this tx the processing queue so we can process it
        self.node.main_processing_queue.append(tx=tx_message_1)
        self.node.main_processing_queue.append(tx=tx_message_3)

        self.async_sleep(0.1)
        self.node.main_processing_queue.append(tx=tx_message_2)

        self.async_sleep(0.2)

        stu_balance_after = self.node.driver.get(f'currency.balances:{self.stu_wallet.verifying_key}')
        jeff_balance_after = self.node.driver.get(f'currency.balances:{self.jeff_wallet.verifying_key}')
        archer_balance_after = self.node.driver.get(f'currency.balances:{self.archer_wallet.verifying_key}')

        self.assertEqual(str(tx_amount), str(stu_balance_before - stu_balance_after))
        self.assertEqual(str('0.0'), str(jeff_balance_after))
        self.assertEqual(str(tx_amount), str(archer_balance_after))

        debug_reprocessing_results = self.node.debug_reprocessing_results
        self.assertEqual('no_writes', debug_reprocessing_results[hlc_timestamp_3]['reprocess_type'])
        self.assertTrue(debug_reprocessing_results[hlc_timestamp_3]['sent_to_network'])

    def test_reprocessing_should_send_new_results(self):
        # This will validate the nodes sends out new results after reprocessing
        # TX #2 and #3 would have created state but will have different state after #1 is reprocessed
        sent_to_network = {}

        def mock_store_solution_and_send_to_network(processing_results):
            hlc_timestamp = processing_results['hlc_timestamp']
            if sent_to_network.get(hlc_timestamp, None) is None:
                sent_to_network[hlc_timestamp] = []
            tx_result_hash = tx_result_hash_from_tx_result_object(
                tx_result=processing_results['tx_result'],
                hlc_timestamp=processing_results['hlc_timestamp']
            )
            sent_to_network[hlc_timestamp].append(tx_result_hash)
            self.node.mock_store_solution_and_send_to_network(processing_results=processing_results)

        self.create_a_node()
        self.start_all_nodes()

        # stop the validation queue
        self.node.validation_queue.stop()

        # Set the HLC of the last consensus
        self.node.validation_queue.last_hlc_in_consensus = "0"
        self.node.last_processed_hlc = "0"

        # Mock the node's store_solution_and_send_to_network function so we can see if it was called
        self.node.mock_store_solution_and_send_to_network = self.node.store_solution_and_send_to_network
        self.node.store_solution_and_send_to_network = mock_store_solution_and_send_to_network

        tx_amount = 200.1
        tx_args = {
            'to': self.jeff_wallet.verifying_key,
            'wallet': self.stu_wallet,
            'amount': tx_amount
        }

        tx_message_1 = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(**tx_args))
        hlc_timestamp_1 = tx_message_1['hlc_timestamp']

        tx_message_2 = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(**tx_args))
        hlc_timestamp_2 = tx_message_2['hlc_timestamp']

        tx_message_3 = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(**tx_args))
        hlc_timestamp_3 = tx_message_3['hlc_timestamp']

        # add this tx the processing queue so we can process it
        self.node.main_processing_queue.append(tx=tx_message_2)
        self.node.main_processing_queue.append(tx=tx_message_3)

        self.async_sleep(0.1)

        self.node.main_processing_queue.append(tx=tx_message_1)

        self.async_sleep(0.1)

        # Validate that HLC 1 doesn't have the same result as when HCL 2 was processed. This is to validate that
        # result hashes are unique as HCL 1 and 2 have the same starting state and tx payload
        self.assertNotEqual(sent_to_network[hlc_timestamp_1][0], sent_to_network[hlc_timestamp_2][0])

        # Validate the tx result hashes have been updated (re-sent) after reprocessing.
        self.assertNotEqual(sent_to_network[hlc_timestamp_2][0], sent_to_network[hlc_timestamp_2][1])
        self.assertNotEqual(sent_to_network[hlc_timestamp_3][0], sent_to_network[hlc_timestamp_3][1])

    def test_reprocessing_should_not_send_new_results_if_not_reprocessed(self):
        # This will validate the nodes don't resend results after reprocessing (assuming the tx wasn't reprocessed)
        # TX #1 and #3 are related but TX #2 is early and causes reprocessing, but it's state is unrelated to #2 and #3
        sent_to_network = {}

        def mock_store_solution_and_send_to_network(processing_results):
            sent_to_network[processing_results['hlc_timestamp']] = True
            self.node.mock_store_solution_and_send_to_network(processing_results=processing_results)

        self.create_a_node()
        self.start_all_nodes()

        # stop the validation queue
        self.node.validation_queue.stop()

        # Set the HLC of the last consensus
        self.node.validation_queue.last_hlc_in_consensus = "0"
        self.node.last_processed_hlc = "0"

        tx_amount = 200.1

        # Send from Stu to Jeff
        tx_message_1 = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(
            to=self.jeff_wallet.verifying_key,
            wallet=self.stu_wallet,
            amount=tx_amount
        ))
        hlc_timestamp_1 = tx_message_1['hlc_timestamp']

        # Send from Jeff to Oliver
        tx_message_2 = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(
            to=self.oliver_wallet.verifying_key,
            wallet=self.jeff_wallet,
            amount=tx_amount
        ))
        hlc_timestamp_2 = tx_message_2['hlc_timestamp']

        # Send from Send from Stu to Archer
        tx_message_3 = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(
            to=self.archer_wallet.verifying_key,
            wallet=self.stu_wallet,
            amount=tx_amount
        ))
        hlc_timestamp_3 = tx_message_3['hlc_timestamp']

        # add this tx the processing queue so we can process it
        self.node.main_processing_queue.append(tx=tx_message_1)
        self.node.main_processing_queue.append(tx=tx_message_3)

        self.async_sleep(0.1)

        # Mock the node's store_solution_and_send_to_network function so we can see if it was called
        self.node.mock_store_solution_and_send_to_network = self.node.store_solution_and_send_to_network
        self.node.store_solution_and_send_to_network = mock_store_solution_and_send_to_network

        self.node.main_processing_queue.append(tx=tx_message_2)

        self.async_sleep(0.1)

        self.assertFalse(sent_to_network.get(hlc_timestamp_1, False))
        self.assertFalse(sent_to_network.get(hlc_timestamp_3, False))
        self.assertTrue(sent_to_network.get(hlc_timestamp_2, False))

    def test_reprocessing_should_not_send_new_results_if_same_state(self):
        # This will validate the nodes don't resend results after reprocessing a transaction and getting the same state
        # TX #2 and #3 are related and are attempts at sending currency from zero balances (should fail both times)
        # TX #1 is early and will send a balance that TX #2 will send (all of it).
        # TX #3 will reprocess because it read the keys from TX #2's writes and will reprocess the same failed tx (zero
        # balance still.  This will not cause the results to get resent to the network.
        sent_to_network = {}

        def mock_store_solution_and_send_to_network(processing_results):
            sent_to_network[processing_results['hlc_timestamp']] = True
            self.node.mock_store_solution_and_send_to_network(processing_results=processing_results)

        self.create_a_node()
        self.start_all_nodes()

        # stop the validation queue
        self.node.validation_queue.stop()

        # Set the HLC of the last consensus
        self.node.validation_queue.last_hlc_in_consensus = "0"
        self.node.last_processed_hlc = "0"

        tx_amount = 200.1
        # Send from Stu to Jeff

        tx_message_1 = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(
            to=self.jeff_wallet.verifying_key,
            wallet=self.stu_wallet,
            amount=tx_amount
        ))
        hlc_timestamp_1 = tx_message_1['hlc_timestamp']

        # Send from Jeff to Oliver
        tx_message_2 = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(
            to=self.archer_wallet.verifying_key,
            wallet=self.jeff_wallet,
            amount=tx_amount
        ))
        hlc_timestamp_2= tx_message_2['hlc_timestamp']

        # Send from Send from Stu to Archer
        tx_message_3 = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(
            to=self.archer_wallet.verifying_key,
            wallet=self.jeff_wallet,
            amount=tx_amount
        ))
        hlc_timestamp_3 = tx_message_3['hlc_timestamp']

        # add this tx the processing queue so we can process it
        self.node.main_processing_queue.append(tx=tx_message_2)
        self.node.main_processing_queue.append(tx=tx_message_3)
        self.async_sleep(0.1)

        # Mock the node's store_solution_and_send_to_network function so we can see if it was called
        self.node.mock_store_solution_and_send_to_network = self.node.store_solution_and_send_to_network
        self.node.store_solution_and_send_to_network = mock_store_solution_and_send_to_network

        self.node.main_processing_queue.append(tx=tx_message_1)
        self.async_sleep(0.1)

        self.assertTrue(sent_to_network.get(hlc_timestamp_1, False))
        self.assertTrue(sent_to_network.get(hlc_timestamp_2, False))
        self.assertFalse(sent_to_network.get(hlc_timestamp_3, False))


    def test_reprocess_after_hard_apply_earilier_block_with_key_keys(self):
        # Test to make sure we reprocess transactions properly when hard applying am earlier block that has new keys
        # To do this we will create a peer node that processes the transactions in order, and then hard apply those
        # processing results out of order to our tester node.  With the state applied we will then process a tx on the
        # node and then send a new consensus block that is earlier than all the current info.  This should cause
        # reprocessing of the tx we processed ourselves

        # Create and start the nodes
        self.create_a_node(node_num=0)

        m_wallet = Wallet()
        constitution = {
                'masternodes': [m_wallet.verifying_key],
                'delegates': []
            }

        bootnodes = {}
        bootnodes[m_wallet.verifying_key] = 'tcp://127.0.0.1:19002'

        node_peer = self.create_a_node(
            node_num=2,
            constitution=constitution,
            bootnodes=bootnodes
        )

        self.start_all_nodes()

        # Stop the node's validation queue to prevent consensus on our results
        self.node.validation_queue.stop()

        # Create a function to intercept the calling of the send to network function so we can see which HLCs this was
        # called for
        sent_to_network = {}
        def mock_store_solution_and_send_to_network(processing_results):
            sent_to_network[processing_results['hlc_timestamp']] = True
            self.node.mock_store_solution_and_send_to_network(processing_results=processing_results)

        recipient_wallet_1 = Wallet()
        recipient_wallet_2 = Wallet()
        tx_amount = 100.5

        # create processing results from another node. These will be added to create state from consensus.
        # tx_1 will give recipient_wallet_1 the balance to send jeff in tx_4 after reprocessing
        tx_message_1 = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(
            wallet=self.stu_wallet,
            to=recipient_wallet_1.verifying_key,
            amount=tx_amount
        ))
        hlc_timestamp_1 = tx_message_1.get('hlc_timestamp')

        processing_results_1 = self.process_a_tx(node=node_peer, tx_message=tx_message_1)
        node_peer.main_processing_queue.append(tx=tx_message_1)

        tx_message_2 = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(
            wallet=self.stu_wallet,
            to=recipient_wallet_2.verifying_key,
            amount=tx_amount
        ))
        hlc_timestamp_2 = tx_message_2.get('hlc_timestamp')
        processing_results_2 = self.process_a_tx(node=node_peer, tx_message=tx_message_2)

        tx_message_3 = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(
            wallet=self.stu_wallet,
            to=recipient_wallet_2.verifying_key,
            amount=tx_amount
        ))
        hlc_timestamp_3 = tx_message_3.get('hlc_timestamp')
        processing_results_3 = self.process_a_tx(node=node_peer, tx_message=tx_message_3)

        # This will fail the first time we run it because we don't know that recipient_wallet_1 has a balance until
        # tx_1 is processed via consensus
        tx_message_4 = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(
            wallet=recipient_wallet_1,
            to=self.jeff_wallet.verifying_key,
            amount=tx_amount
        ))
        hlc_timestamp_4 = tx_message_4.get('hlc_timestamp')

        # Hard apply these processing results to get some state on our tester node
        self.await_hard_apply_block(node=self.node, processing_results=processing_results_2)
        # Validate state was applied
        recipient_2_balance = self.node.driver.get(key=f'currency.balances:{recipient_wallet_2.verifying_key}')
        self.assertEqual(str(tx_amount), str(recipient_2_balance))

        self.await_hard_apply_block(node=self.node, processing_results=processing_results_3)
        # Validate state was applied
        recipient_2_balance = self.node.driver.get(key=f'currency.balances:{recipient_wallet_2.verifying_key}')
        self.assertEqual(str(tx_amount*2), str(recipient_2_balance))

        # Validate both blocks processed
        self.assertIsNotNone(2, self.node.get_current_height())
        self.assertIsNotNone(hlc_timestamp_3, self.node.last_processed_hlc)

        # Process tx4 through the tester node so we get a result
        self.node.main_processing_queue.append(tx=tx_message_4)
        self.async_sleep(0.1)

        # Mock the node's store_solution_and_send_to_network function so we can see if it was called
        self.node.mock_store_solution_and_send_to_network = self.node.store_solution_and_send_to_network
        self.node.store_solution_and_send_to_network = mock_store_solution_and_send_to_network

        # Apply the earlier block to our tester node
        self.await_hard_apply_block(node=self.node, processing_results=processing_results_1)

        # Restart Validation Queue to get consensus on the latest message
        self.node.validation_queue.start()
        self.async_sleep(0.1)

        # Validate state balances are as expected after reprocessing
        recipient_1_balance = self.node.driver.get(key=f'currency.balances:{recipient_wallet_1.verifying_key}')
        recipient_2_balance = self.node.driver.get(key=f'currency.balances:{recipient_wallet_2.verifying_key}')
        jeff_balance = self.node.driver.get(key=f'currency.balances:{self.jeff_wallet.verifying_key}')

        self.assertEqual('0.0', str(recipient_1_balance))
        self.assertEqual(str(tx_amount * 2), str(recipient_2_balance))
        self.assertEqual(str(tx_amount), str(jeff_balance))

        # Validate out new solution was sent to the rest of the nodes
        self.assertTrue(sent_to_network[hlc_timestamp_4])