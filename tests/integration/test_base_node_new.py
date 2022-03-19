from lamden.nodes.masternode import masternode
from lamden.nodes import base, filequeue
from lamden.nodes.masternode.masternode import Masternode
from lamden import storage
from lamden.crypto.wallet import Wallet
from lamden.crypto import transaction

from contracting.db.driver import InMemDriver, ContractDriver

from contracting.db import encoder

import asyncio

import json
from pathlib import Path
from lamden.crypto.wallet import verify
from lamden.crypto.canonical import tx_hash_from_tx, block_from_tx_results
from tests.integration.mock.create_directories import remove_fixture_directories
from tests.unit.helpers.mock_transactions import get_new_currency_tx, get_tx_message, get_processing_results

from operator import itemgetter

from unittest import TestCase

DEFAULT_HASH = f'0' * 64
DEFAULT_BLOCk = 0

class TestNode(TestCase):
    def setUp(self):
        self.num_of_nodes = 0

        self.state = storage.StateManager()

        self.mn_wallet = Wallet()
        self.fixture_directories = ['txq']

        self.current_path = Path.cwd()
        self.file_queue_path = f'{self.current_path}/fixtures/file_queue'
        self.tx_queue_path = f'{self.file_queue_path}/{self.mn_wallet.verifying_key}/txq'

        self.stu_wallet = Wallet()
        self.jeff_wallet = Wallet()
        self.archer_wallet = Wallet()

        self.b = masternode.BlockService(
            state=self.state
        )

        self.state.blocks.flush()
        self.state.driver.flush()

        self.node = None
        self.nodes = []

        print("\n")

    def tearDown(self):
        for node in self.nodes:
            if (node.running):
                self.await_async_process(node.stop)

        self.b.state.blocks.flush()
        self.b.state.driver.flush()

        remove_fixture_directories(
            root=self.file_queue_path,
            dir_list=[self.mn_wallet.verifying_key]
        )

    def create_a_node(self, bootnodes=None, constitution=None, node_num=0, node_type='base'):
        driver = ContractDriver(driver=InMemDriver())

        dl_wallet = Wallet()

        constitution = constitution or {
                'masternodes': [self.mn_wallet.verifying_key],
                'delegates': []
            }

        if bootnodes is None:
            bootnodes = {}
            bootnodes[self.mn_wallet.verifying_key] = f'tcp://127.0.0.1:{19000 + node_num}'

        if node_type == 'base':
            node = base.Node(
                socket_base=f'tcp://127.0.0.1:{19000 + node_num}',
                wallet=self.mn_wallet,
                constitution=constitution,
                testing=True,
                metering=False,
                delay={
                    'base': 0,
                    'self': 0
                },
                tx_queue=filequeue.FileQueue(root=self.tx_queue_path),
                bootnodes=bootnodes
            )

        if node_type == 'masternode':
            node = Masternode(
                socket_base=f'tcp://127.0.0.1:{19000 + node_num}',
                wallet=self.mn_wallet,
                constitution=constitution,
                testing=True,
                metering=False,
                delay={
                    'base': 0,
                    'self': 0
                },
                tx_queue=filequeue.FileQueue(root=self.tx_queue_path),
                bootnodes=bootnodes
            )

        if node_num > 0:
            node.network.set_socket_port(service='router', port_num=19000 + node_num)
            node.network.set_socket_port(service='webserver', port_num=18080 + node_num)
            node.network.set_socket_port(service='publisher', port_num=19080 + node_num)

        node.state.client.set_var(
            contract='currency',
            variable='balances',
            arguments=[self.stu_wallet.verifying_key],
            value=1_000_000
        )

        node.state.client.set_var(
            contract='currency',
            variable='balances',
            arguments=[self.stu_wallet.verifying_key],
            value=1_000_000
        )

        node.state.driver.commit()

        self.nodes.append(node)

        self.num_of_nodes = self.num_of_nodes + 1

        if node_num > 0:
            return node
        else:
            self.node = node

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

    def start_nodes(self):
        for node in self.nodes:
            self.await_async_process(node.start)

    def start_node(self, node=None):
        if (node):
            print("other node")
            self.await_async_process(node.start)
        else:
            print("self node")
            self.await_async_process(self.node.start)

    def stop_node(self, node=None):
        if (node):
            self.await_async_process(node.stop)
        else:
            self.await_async_process(self.node.stop)

    def add_solution(self, node, tx=None, tx_message=None, wallet=None, amount=None, to=None, receiver_wallet=None,
                     node_wallet=None, masternode=None, processing_results=None):

        masternode = masternode or Wallet()
        receiver_wallet = receiver_wallet or Wallet()
        node_wallet = node_wallet or Wallet()

        wallet = wallet or Wallet()
        amount = amount or "10.5"
        to = to or receiver_wallet.verifying_key

        if tx_message is None:
            transaction = tx or get_new_currency_tx(wallet=wallet, amount=amount, to=to)

        tx_message = tx_message or get_tx_message(tx=transaction, node_wallet=masternode)

        processing_results = processing_results or get_processing_results(tx_message=tx_message, node_wallet=node_wallet)

        node.validation_queue.append(processing_results=processing_results)

        return processing_results

    def get_processing_results(self, node, hlc_timestamp, node_vk):
        solution = node.validation_queue.validation_results[hlc_timestamp]['solutions'][node_vk]
        return node.validation_queue.validation_results[hlc_timestamp]['result_lookup'][solution]

    def process_a_tx(self, node, tx_message):
        processing_results = get_processing_results(node=node, tx_message=tx_message)
        hlc_timestamp = processing_results.get('hlc_timestamp')

        node.last_processed_hlc = hlc_timestamp
        node.soft_apply_current_state(hlc_timestamp=hlc_timestamp)

        node.store_solution_and_send_to_network(processing_results=processing_results)

        self.async_sleep(0.01)

        return processing_results

    def await_hard_apply_block(self, node, processing_results):
        tasks = asyncio.gather(
            node.hard_apply_block(processing_results=processing_results)
        )
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)
        return res

    def test_started(self):
        self.create_a_node()
        self.start_node()

        self.assertTrue(self.node.running)

    def test_stopped(self):
        self.create_a_node()
        self.start_node()
        self.stop_node()

        self.assertFalse(self.node.running)

    def test_make_tx_message(self):
        self.create_a_node()
        self.start_node()

        tx_message = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(
            wallet=self.stu_wallet,
            to=self.jeff_wallet.verifying_key,
            amount=100.5
        ))

        tx, hlc_timestamp, signature, sender = itemgetter(
            'tx', 'hlc_timestamp', 'signature', 'sender'
        )(tx_message)

        self.assertIsNotNone(tx)
        self.assertIsNotNone(hlc_timestamp)
        self.assertIsNotNone(signature)
        self.assertIsNotNone(sender)

        tx_hash = tx_hash_from_tx(tx)
        self.assertTrue(verify(vk=sender, msg=f'{tx_hash}{hlc_timestamp}', signature=signature))

    def test_check_main_processing_queue(self):
        self.create_a_node()
        self.start_node()

        # stop the validation queue
        self.node.validation_queue.stop()

        tx_message = self.node.main_processing_queue.make_tx_message(tx=get_new_currency_tx(
            wallet=self.stu_wallet,
            to=self.jeff_wallet.verifying_key,
            amount=100.5
        ))

        hlc_timestamp = tx_message['hlc_timestamp']

        # add this tx the processing queue so we can process it
        self.node.main_processing_queue.append(tx=tx_message)

        self.async_sleep(0.05)

        # tx was processed
        self.assertEqual(0, len(self.node.main_processing_queue))
        print({
            'hlc_timestamp': hlc_timestamp,
            'last_processed_hlc': self.node.state.metadata.last_processed_hlc
        })
        self.assertEqual(hlc_timestamp, self.node.state.metadata.last_processed_hlc)

    def test_check_main_processing_queue_not_process_while_stopped(self):
        self.create_a_node()
        self.start_node()

        # Stop the main processing queue
        self.node.main_processing_queue.stop()
        self.await_async_process(self.node.main_processing_queue.stopping)

        tx_message = self.node.main_processing_queue.make_tx_message(tx=get_new_currency_tx(
            wallet=self.stu_wallet,
            to=self.jeff_wallet.verifying_key,
            amount=100.5
        ))
        hlc_timestamp = tx_message['hlc_timestamp']

        # add this tx the processing queue
        self.node.main_processing_queue.append(tx=tx_message)

        self.async_sleep(0.05)

        # tx was not processed
        self.assertEqual(1, len(self.node.main_processing_queue))
        self.assertNotEqual(hlc_timestamp, self.node.state.metadata.last_processed_hlc)

    def test_check_main_processing_queue_skips_hcl_if_less_than_in_consensus(self):
        self.create_a_node()
        self.start_node()

        # stop the validation queue
        self.node.validation_queue.stop()


        tx_message = self.node.main_processing_queue.make_tx_message(tx=get_new_currency_tx(
            wallet=self.stu_wallet,
            to=self.jeff_wallet.verifying_key,
            amount=100.5
        ))

        hlc_timestamp_later = self.node.hlc_clock.get_new_hlc_timestamp()

        # Set the HLC of the last consensus
        self.node.validation_queue.last_hlc_in_consensus = hlc_timestamp_later

        # add this tx the processing queue so we can process it
        self.node.main_processing_queue.append(tx=tx_message)

        self.async_sleep(0.05)

        # tx was processed
        self.assertEqual(0, len(self.node.main_processing_queue))

        # Nothing was added to the validation queue
        self.assertEqual(0, len(self.node.validation_queue))

        # last HLC in consensus still 2
        self.assertEqual(hlc_timestamp_later, self.node.validation_queue.last_hlc_in_consensus)

    def test_check_validation_queue(self):
        self.create_a_node()
        self.node.consensus_percent = 0

        self.start_node()

        tx_message = self.node.main_processing_queue.make_tx_message(tx=get_new_currency_tx(
            wallet=self.stu_wallet,
            to=self.jeff_wallet.verifying_key,
            amount=100.5
        ))

        hlc_timestamp = tx_message.get('hlc_timestamp')

        self.add_solution(
            node=self.node,
            tx_message=tx_message
        )

        #wait for pocessing to complete
        self.async_sleep(0.05)

        # tx was processed
        self.assertEqual(0, len(self.node.validation_queue))
        self.assertEqual(hlc_timestamp, self.node.state.metadata.last_hlc_in_consensus)

    def test_check_validation_queue_not_processed_when_stopped(self):
        self.create_a_node()
        self.node.consensus_percent = 0

        tx_message = self.node.main_processing_queue.make_tx_message(tx=get_new_currency_tx(
            wallet=self.stu_wallet,
            to=self.jeff_wallet.verifying_key,
            amount=100.5
        ))

        hlc_timestamp = tx_message.get('hlc_timestamp')

        self.add_solution(
            node=self.node,
            tx_message=tx_message
        )

        #wait for pocessing to complete
        self.async_sleep(0.05)

        # tx was processed
        self.assertEqual(1, len(self.node.validation_queue))
        self.assertNotEqual(hlc_timestamp, self.node.state.metadata.last_hlc_in_consensus)

    def test_increments_block_after_consensus(self):
        self.create_a_node()
        self.node.consensus_percent = 0

        print(f'Starting HLC: {self.node.last_processed_hlc}')

        self.start_node()

        tx_message = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(
            wallet=self.stu_wallet,
            to=self.jeff_wallet.verifying_key,
            amount=100.5
        ))

        hlc_timestamp = tx_message.get('hlc_timestamp')

        self.node.main_processing_queue.append(tx_message)

        #wait for pocessing to complete
        self.async_sleep(0.01)

        # queue is empty because tx was processed
        self.assertEqual(hlc_timestamp, self.node.last_processed_hlc)

        # queue is empty because tx was processed
        self.assertEqual(0, len(self.node.validation_queue))

        # Both the queue and the node report the block height is now one, as per the driver
        self.assertEqual(1, self.node.get_current_height())

    def test_update_block_db(self):
        self.create_a_node()
        self.node.consensus_percent = 0

        self.start_node()

        block_info = {
            'hash': '1' * 64,
            'number': 1
        }
        self.node.update_block_db(block_info)

        # Both the queue and the node report the block height is now one, as per the driver
        self.assertEqual(block_info.get('number'), self.node.get_current_height())

        # Both the queue and the node report the block height is now one, as per the driver
        self.assertEqual(block_info.get('hash'), self.node.get_current_hash())

    def test_soft_apply_current_state(self):
        self.create_a_node()
        self.start_node()

        #stop the queues
        self.node.main_processing_queue.stop()
        self.node.validation_queue.stop()

        # create a transaction
        recipient_wallet = Wallet()
        tx_amount = 200.5

        tx_message = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(
            wallet=self.stu_wallet,
            to=recipient_wallet.verifying_key,
            amount=tx_amount
        ))

        hlc_timestamp = tx_message.get('hlc_timestamp')

        # Add the tx to the stopped processing queue
        self.node.main_processing_queue.append(tx=tx_message)

        # wait the amount of delay before the queue will process the transaction
        self.async_sleep(0.05)

        # Process the transaction and get the result
        self.await_async_process(self.node.main_processing_queue.process_next)

        # Run the Soft Apply logic
        self.node.soft_apply_current_state(hlc_timestamp)

        # Get the recipient balance from the driver
        recipient_balance_after = self.node.executor.driver.get_var(
            contract='currency',
            variable='balances',
            arguments=[recipient_wallet.verifying_key],
            mark=False
        )

        # The recipient's balance was updated
        self.assertEqual(tx_amount, recipient_balance_after)

        # TODO Test cases for rewarded wallet prior state changes

    def test_state_values_after_multiple_transactions(self):
        self.create_a_node()
        self.start_node()

        print("sending first transaction")
        # ___ SEND 1 Transaction ___
        # create a transaction
        recipient_wallet = Wallet()
        tx_amount = 100.5

        tx_message = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(
            wallet=self.stu_wallet,
            to=recipient_wallet.verifying_key,
            amount=tx_amount
        ))

        # add to processing queue
        self.node.main_processing_queue.append(tx=tx_message)
        # wait the amount of delay before the queue will process the transaction
        self.async_sleep(1)
        self.assertEqual(0, len(self.node.main_processing_queue))

        # Get the recipient balance from the driver
        recipient_balance_after = self.node.executor.driver.get_var(
            contract='currency',
            variable='balances',
            arguments=[recipient_wallet.verifying_key],
            mark=False
        )
        recipient_balance_after = json.loads(encoder.encode(recipient_balance_after))['__fixed__']

        # The recipient's balance was updated
        self.assertEqual("100.5", recipient_balance_after)
        # The block was incremented
        self.assertEqual(1, self.node.get_current_height())
        self.assertEqual(0, len(self.node.main_processing_queue))

        print("sending second transaction")
        # ___ SEND ANOTHER Transaction ___
        # create a transaction
        tx_message_2 = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(
            wallet=self.stu_wallet,
            to=recipient_wallet.verifying_key,
            amount=tx_amount
        ))

        hlc_timestamp_2 = tx_message_2.get('hlc_timestamp')

        # add to processing queue
        self.node.main_processing_queue.append(tx=tx_message_2)
        # wait the amount of delay before the queue will process the transaction
        self.async_sleep(1)
        self.assertEqual(0, len(self.node.main_processing_queue))

        # Get the recipient balance from the driver
        recipient_balance_after = self.node.executor.driver.get_var(
            contract='currency',
            variable='balances',
            arguments=[recipient_wallet.verifying_key],
            mark=False
        )
        recipient_balance_after = json.loads(encoder.encode(recipient_balance_after))['__fixed__']

        # The recipient's balance was updated
        self.assertEqual("201.0", recipient_balance_after)
        # The block was incremented
        self.assertEqual(2, self.node.get_current_height())

        # tx_message_2 is the last hlc processed and in consensus
        self.assertEqual(hlc_timestamp_2, self.node.last_processed_hlc)
        self.assertEqual(hlc_timestamp_2, self.node.validation_queue.last_hlc_in_consensus)

    def test_rollback_drivers(self):
        self.create_a_node()
        # Set the consensus percent to 0 so all processed transactions will "be in consensus"
        self.node.consensus_percent = 0

        self.start_node()

        # Stop the validation queue so we don't mint blocks
        self.node.validation_queue.stop()

        # ___ SEND 1 Transaction ___
        # create a transaction
        recipient_wallet = Wallet()
        tx_amount = 100.5

        tx_message = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(
            wallet=self.stu_wallet,
            to=recipient_wallet.verifying_key,
            amount=tx_amount
        ))
        hlc_timestamp_1 = tx_message.get('hlc_timestamp')

        # add to processing queue
        self.node.main_processing_queue.append(tx=tx_message)
        # wait the amount of delay before the queue will process the transaction
        self.async_sleep(1)
        self.assertEqual(0, len(self.node.main_processing_queue))

        # ___ SEND ANOTHER Transaction ___
        # create a transaction
        tx_message_2 = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(
            wallet=self.stu_wallet,
            to=recipient_wallet.verifying_key,
            amount=tx_amount
        ))

        hlc_timestamp_2 = tx_message_2.get('hlc_timestamp')

        # Stop the validation queue so this this transaction doesn't have consensus performed. The assumption is that we
        # are not in consensus and need to rollback to previous transaction.
        self.node.validation_queue.stop()

        # add to processing queue
        self.node.main_processing_queue.append(tx=tx_message_2)

        # wait the amount of delay before the queue will process the transaction
        self.async_sleep(1)
        self.assertEqual(0, len(self.node.main_processing_queue))

        # Get the recipient balance from the driver
        recipient_balance_after = self.node.executor.driver.get_var(
            contract='currency',
            variable='balances',
            arguments=[recipient_wallet.verifying_key],
            mark=False
        )
        recipient_balance_after = json.loads(encoder.encode(recipient_balance_after))['__fixed__']

        # --- TESTS TO MAKE SURE THE SETUP BEFORE ROLLBACK IS LEGIT ---
        # The recipient's balance was updated
        self.assertEqual("201.0", recipient_balance_after)
        self.assertEqual(hlc_timestamp_2, self.node.last_processed_hlc)
        # ---

        # Initiate rollback to block 1 (hlc_timestamp_1) test state values
        # to prevent auto processing and allow us to test the state of them after the rollback
        self.node.main_processing_queue.stop()

        self.node.rollback_drivers(hlc_timestamp=hlc_timestamp_2)

        # --- TEST STATE AFTER ROLLBACK DRIVERS ---

        # Get the recipient balance from the driver
        recipient_balance_after_rollback = self.node.executor.driver.get_var(
            contract='currency',
            variable='balances',
            arguments=[recipient_wallet.verifying_key],
            mark=False
        )
        recipient_balance_after_rollback = json.loads(encoder.encode(recipient_balance_after_rollback))['__fixed__']

        # The recipient's balance was updated
        self.assertEqual("100.5", recipient_balance_after_rollback)

    def test_hard_apply_next_block(self):
        # Create a node and start it
        self.create_a_node()

        recipient_wallet = Wallet()
        tx_amount = 100.5

        self.start_node()

        #stop the validation queue because we want to call hard apply ourselves
        self.node.validation_queue.stop()

        # create a transaction and send it to create a pending delta
        tx_message_1 = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(
            wallet=self.stu_wallet,
            to=recipient_wallet.verifying_key,
            amount=tx_amount
        ))
        hlc_timestamp_1 = tx_message_1.get('hlc_timestamp')

        self.node.main_processing_queue.append(tx_message_1)

        # wait for processing
        self.async_sleep(0.21)

        # Validate pending delta exits
        self.assertIsNotNone(self.node.driver.pending_deltas.get(hlc_timestamp_1))

        processing_results = self.get_processing_results(
            node=self.node,
            hlc_timestamp=hlc_timestamp_1,
            node_vk=self.node.wallet.verifying_key
        )

        # Validate delta applied
        self.await_hard_apply_block(node=self.node, processing_results=processing_results)

        # Validate block height in cache
        self.assertEqual(1, self.node.driver.get('_current_block_height'))

        # Validate pending delta was applied
        self.assertIsNone(self.node.driver.pending_deltas.get(hlc_timestamp_1))

        # Validate
        self.assertEqual(1, self.node.get_current_height())

    def test_hard_apply_earlier_block__all_keys_overwritten(self):
        # Test hard applying blocks that come in from consensus earlier than blocks we already have
        # To do this we will create a peer node that processed the transactions in order, and then hard apply those
        # processing results out of order to our tester node

        # Create and start the nodes
        self.create_a_node()
        self.start_node()

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
        self.start_node(node=node_peer)

        recipient_wallet = Wallet()
        tx_amount = 100.5

        # create processing results from another node. These will be added to create state from consensus.
        tx_message_1 = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(
            wallet=self.stu_wallet,
            to=recipient_wallet.verifying_key,
            amount=tx_amount
        ))
        hlc_timestamp_1 = tx_message_1.get('hlc_timestamp')
        processing_results_1 = self.process_a_tx(node=node_peer, tx_message=tx_message_1)

        tx_message_2 = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(
            wallet=self.stu_wallet,
            to=recipient_wallet.verifying_key,
            amount=tx_amount
        ))
        hlc_timestamp_2 = tx_message_2.get('hlc_timestamp')
        processing_results_2 = self.process_a_tx(node=node_peer, tx_message=tx_message_2)

        tx_message_3 = make_tx_message(self.node.hlc_clock, self.node.wallet, tx=get_new_currency_tx(
            wallet=self.stu_wallet,
            to=recipient_wallet.verifying_key,
            amount=tx_amount
        ))
        hlc_timestamp_3 = tx_message_3.get('hlc_timestamp')
        processing_results_3 = self.process_a_tx(node=node_peer, tx_message=tx_message_3)

        # Hard apply these processing results to get some state on our tester node
        self.await_hard_apply_block(node=self.node, processing_results=processing_results_2)
        self.await_hard_apply_block(node=self.node, processing_results=processing_results_3)

        # Validate both blocks processed
        self.assertIsNotNone(2, self.node.get_current_height())
        self.assertIsNotNone(hlc_timestamp_3, self.node.last_processed_hlc)

        # Apply the earlier block to our tester node
        self.await_hard_apply_block(node=self.node, processing_results=processing_results_1)

        # Validate the block was processed
        # block height is now 3
        self.assertIsNotNone(3, self.node.get_current_height())

        block_1 = self.node.blocks.get_block(v=1)
        block_2 = self.node.blocks.get_block(v=2)
        block_3 = self.node.blocks.get_block(v=3)

        self.assertEqual(hlc_timestamp_1, block_1.get('hlc_timestamp'))
        self.assertEqual(hlc_timestamp_2, block_2.get('hlc_timestamp'))
        self.assertEqual(hlc_timestamp_3, block_3.get('hlc_timestamp'))

        # Validate no state was overwritten
        recipient_balance = self.node.driver.get(key=f'currency.balances:{recipient_wallet.verifying_key}')
        self.assertEqual(str(tx_amount*3), str(recipient_balance))

        self.await_async_process(node_peer.stop)

    def test_hard_apply_earlier_block__earlier_tx_has_new_keys(self):
        # Test hard applying blocks that come in from consensus earlier than blocks we already have
        # To do this we will create a peer node that processed the transactions in order, and then hard apply those
        # processing results out of order to our tester node

        # Create and start the nodes
        self.create_a_node(node_num=0)
        node_peer = self.create_a_node(node_num=1)

        self.start_nodes()

        recipient_wallet_1 = Wallet()
        recipient_wallet_2 = Wallet()
        tx_amount = 100.5

        # create processing results from another node. These will be added to create state from consensus.
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

        # Apply the earlier block to our tester node
        self.await_hard_apply_block(node=self.node, processing_results=processing_results_1)

        # Validate the block was processed
        # block height is now 3
        self.assertIsNotNone(3, self.node.get_current_height())

        block_1 = self.node.blocks.get_block(v=1)
        block_2 = self.node.blocks.get_block(v=2)
        block_3 = self.node.blocks.get_block(v=3)

        self.assertEqual(hlc_timestamp_1, block_1.get('hlc_timestamp'))
        self.assertEqual(hlc_timestamp_2, block_2.get('hlc_timestamp'))
        self.assertEqual(hlc_timestamp_3, block_3.get('hlc_timestamp'))

        # Validate no state was overwritten
        recipient_2_balance = self.node.driver.get(key=f'currency.balances:{recipient_wallet_2.verifying_key}')
        self.assertEqual(str(tx_amount*2), str(recipient_2_balance))

        # Validate new state was created
        recipient_1_balance = self.node.driver.get(key=f'currency.balances:{recipient_wallet_1.verifying_key}')
        self.assertEqual(str(tx_amount), str(recipient_1_balance))

        self.await_async_process(node_peer.stop)

    def test_get_current_height(self):
        # Create a node and start it
        self.create_a_node()
        self.start_node()

        # Height is None
        self.assertIsNone(None, self.node.get_current_height())

        # create a transaction and send it to create a pending delta
        tx_message_1 = self.node.main_processing_queue.make_tx_message(tx=get_new_currency_tx(
            wallet=self.stu_wallet,
            to=self.jeff_wallet.verifying_key,
            amount=100.5
        ))
        self.node.main_processing_queue.append(tx_message_1)
        # wait for processing
        self.async_sleep(0.21)

        # Validate
        self.assertEqual(1, self.node.get_current_height())

    def test_get_current_hash(self):
        # Create a node and start it
        self.create_a_node()
        self.start_node()

        # Hash Is None
        self.assertEqual(DEFAULT_HASH, self.node.get_current_hash())

        # create a transaction and send it to create a pending delta
        tx_message_1 = self.node.main_processing_queue.make_tx_message(tx=get_new_currency_tx(
            wallet=self.stu_wallet,
            to=self.jeff_wallet.verifying_key,
            amount=100.5
        ))
        self.node.main_processing_queue.append(tx_message_1)
        # wait for processing
        self.async_sleep(0.21)

        # Validate
        self.assertNotEqual(DEFAULT_HASH, self.node.get_current_hash())

    def test_processes_transactions_from_files(self):
        # Create a node and start it
        self.create_a_node(node_type='masternode')
        self.start_node()

        receiver_wallet = Wallet()

        tx_str = transaction.build_transaction(
            wallet= Wallet(),
            contract='currency',
            function='transfer',
            kwargs={
                'to': receiver_wallet.verifying_key,
                'amount': {'__fixed__': '100.5'}
            },
            stamps=100,
            processor=self.node.wallet.verifying_key,
            nonce=1
        )

        self.node.tx_queue.append(tx=tx_str.encode())

        self.async_sleep(0.3)

        # Validate
        self.assertEqual(1, self.node.get_current_height())

    def test_get_peers_for_consensus(self):
        d_wallet = Wallet()
        constitution = {
                'masternodes': [self.mn_wallet.verifying_key],
                'delegates': [d_wallet.verifying_key]
            }

        bootnodes = {}
        bootnodes[self.mn_wallet.verifying_key] = f'tcp://127.0.0.1:19000'
        bootnodes[d_wallet.verifying_key] = f'tcp://127.0.0.1:19001'


        self.create_a_node(constitution=constitution, bootnodes=bootnodes, node_type='masternode')
        self.start_node()

        for vk in self.node.network.peers:
            self.node.network.peers[vk].running = True

        peers_for_consensus = self.node.get_peers_for_consensus()

        self.assertEqual(1, len(peers_for_consensus))