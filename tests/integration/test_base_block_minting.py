from lamden.crypto.wallet import Wallet
from tests.integration.mock.threaded_node import create_a_node, ThreadedNode
from tests.unit.helpers.mock_transactions import get_new_currency_tx, get_processing_results
from unittest import TestCase
import asyncio
import json

class TestNode(TestCase):
    def setUp(self):
        self.stu_wallet = Wallet()
        self.jeff_wallet = Wallet()
        self.oliver_wallet = Wallet()
        self.archer_wallet = Wallet()

        self.threaded_nodes = []

    def tearDown(self):
        for tn in self.threaded_nodes:
            self.await_async_process(tn.stop)

    def create_node(self, index=0):
        tn = create_a_node(index=index)
        tn.set_smart_contract_value(f'currency.balances:{self.stu_wallet.verifying_key}', value=1_000_000)
        self.threaded_nodes.append(tn)

        return tn

    def start_node(self, tn: ThreadedNode):
        tn.start()

        while not tn.node or not tn.node.started or not tn.node.network.running:
            self.await_async_process(asyncio.sleep, 1)

    def create_and_start_node(self, index=0):
        tn = self.create_node(index=index)
        self.start_node(tn)

        return tn

    def await_async_process(self, process, *args, **kwargs):
        tasks = asyncio.gather(
            process(*args, **kwargs)
        )
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)
        return res

    def await_node_reaches_height(self, tn: ThreadedNode, height):
        while tn.blocks.total_blocks() != height:
            self.await_async_process(asyncio.sleep, 0.1)

    def test_hard_apply_block(self):
        # Hard Apply will mint a new block, apply state and increment block height
        tn = self.create_and_start_node()

        stu_balance_before = tn.get_smart_contract_value(f'currency.balances:{self.stu_wallet.verifying_key}')

        tx_amount = 200.1
        tx_args = {
            'to': self.jeff_wallet.verifying_key,
            'wallet': self.stu_wallet,
            'amount': tx_amount,
            'processor': tn.wallet.verifying_key
        }

        tn.send_tx(json.dumps(get_new_currency_tx(**tx_args)).encode())

        self.await_node_reaches_height(tn, 1)

        block = tn.blocks.get_block(v=tn.latest_block_height)

        self.assertIsNotNone(block)

        self.assertEqual(tx_amount, tn.get_smart_contract_value(f'currency.balances:{self.jeff_wallet.verifying_key}'))
        self.assertEqual(stu_balance_before - tx_amount, tn.get_smart_contract_value(f'currency.balances:{self.stu_wallet.verifying_key}'))
        self.assertEqual(1, tn.blocks.total_blocks())

    def test_hard_apply_block_multiple_concurrent(self):
        # Hard Apply will mint new blocks, apply state and increment block height after multiple transactions
        tn = self.create_and_start_node()

        stu_balance_before = tn.get_smart_contract_value(f'currency.balances:{self.stu_wallet.verifying_key}')

        tx_amount = 200.1
        # Send from Stu to Jeff
        tx_messages = []
        tx_messages.append(get_new_currency_tx(
            to=self.jeff_wallet.verifying_key,
            wallet=self.stu_wallet,
            amount=tx_amount,
            processor=tn.wallet.verifying_key,
            nonce=1
        ))

        # Send from Jeff to Archer
        tx_messages.append(get_new_currency_tx(
            to=self.archer_wallet.verifying_key,
            wallet=self.jeff_wallet,
            amount=tx_amount,
            processor=tn.wallet.verifying_key,
            nonce=2
        ))

        # Send from Archer to Oliver
        tx_messages.append(get_new_currency_tx(
            to=self.oliver_wallet.verifying_key,
            wallet=self.archer_wallet,
            amount=tx_amount,
            processor=tn.wallet.verifying_key,
            nonce=3
        ))

        for tx_message in tx_messages:
            tn.send_tx(json.dumps(tx_message).encode())

        self.await_node_reaches_height(tn, 3)

        self.assertEqual(3, tn.blocks.total_blocks())

        self.assertEqual(stu_balance_before - tx_amount, tn.get_smart_contract_value(f'currency.balances:{self.stu_wallet.verifying_key}'))
        self.assertEqual(0, tn.get_smart_contract_value(f'currency.balances:{self.jeff_wallet.verifying_key}'))
        self.assertEqual(0, tn.get_smart_contract_value(f'currency.balances:{self.archer_wallet.verifying_key}'))
        self.assertEqual(tx_amount, tn.get_smart_contract_value(f'currency.balances:{self.oliver_wallet.verifying_key}'))

''' NOTE: Probably N\A anymore but let's see.

    def test_hard_apply_block_multiple_nonconcurrent(self):
        # Hard Apply will mint new blocks, apply state and increment block height after multiple transactions that come
        # in out of order
        # have a node process the results correctly and then add them to another node out of order

        # This node we will use for the testing
        node_1 = self.create_and_start_node()

        # This node we will use to create the processing results which will be passed to node_1
        node_2 = self.create_and_start_node(index=1)

        stu_balance_before = node_2.get_smart_contract_value(f'currency.balances:{self.stu_wallet.verifying_key}')

        # Create three transactions
        tx_amount = 200.1
        # Send from Stu to Jeff
        tx_message_1 = node_2.node.make_tx_message(tx=get_new_currency_tx(
            to=self.jeff_wallet.verifying_key,
            wallet=self.stu_wallet,
            amount=tx_amount
        ))
        hlc_timestamp_1 = tx_message_1.get('hlc_timestamp')

        # Send from Jeff to Archer
        tx_message_2 = node_2.node.make_tx_message(tx=get_new_currency_tx(
            to=self.archer_wallet.verifying_key,
            wallet=self.jeff_wallet,
            amount=tx_amount
        ))
        hlc_timestamp_2 = tx_message_2.get('hlc_timestamp')

        # Send from Archer to Oliver
        tx_message_3 = node_2.node.make_tx_message(tx=get_new_currency_tx(
            to=self.oliver_wallet.verifying_key,
            wallet=self.archer_wallet,
            amount=tx_amount
        ))
        hlc_timestamp_3 = tx_message_3.get('hlc_timestamp')

        ## Have node 2 process the transactions in order to generate the results
        processing_results_1 = get_processing_results(tx_message_1, node=node_2)
        processing_results_2 = get_processing_results(tx_message_2, node=node_2)
        processing_results_3 = get_processing_results(tx_message_3, node=node_2)

        # Add results from TX2 and TX3
        node_1.validation_queue.append(processing_results_2)
        node_1.validation_queue.append(processing_results_3)

        # Await processing and consensus
        self.await_node_reaches_height(node_1, 2)

        # Validate blocks are created
        self.assertIsNotNone(node_1.blocks.get_block(v=1))
        self.assertIsNotNone(node_1.blocks.get_block(v=2))

        # Add results from TX1
        node_1.validation_queue.append(processing_results_1)

        # Await processing and consensus
        self.await_node_reaches_height(node_1, 3)

        # Validate the blocks are in hlc_timestamps order
        block_1 = node_1.blocks.get_block(v=1)
        block_2 = node_1.blocks.get_block(v=2)
        block_3 = node_1.blocks.get_block(v=3)
        self.assertEqual(hlc_timestamp_1, block_1.get('hlc_timestamp'))
        self.assertEqual(hlc_timestamp_2, block_2.get('hlc_timestamp'))
        self.assertEqual(hlc_timestamp_3, block_3.get('hlc_timestamp'))

        self.assertEqual(stu_balance_before - tx_amount, node_1.get_smart_contract_value(f'currency.balances:{self.stu_wallet.verifying_key}'))
        self.assertEqual(0, node_1.get_smart_contract_value(f'currency.balances:{self.jeff_wallet.verifying_key}'))
        self.assertEqual(0, node_1.get_smart_contract_value(f'currency.balances:{self.archer_wallet.verifying_key}'))
        self.assertEqual(tx_amount, node_1.get_smart_contract_value(f'currency.balances:{self.oliver_wallet.verifying_key}'))
        self.assertEqual(3, node_1.current_height)
'''