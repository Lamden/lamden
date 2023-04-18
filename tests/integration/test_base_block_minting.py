from lamden.crypto.wallet import Wallet
from pathlib import Path
from tests.integration.mock.mock_data_structures import MockBlocks
from tests.integration.mock.threaded_node import create_a_node, ThreadedNode
from tests.unit.helpers.mock_transactions import get_new_currency_tx
from unittest import TestCase
import asyncio
import json
import shutil

class TestNode(TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.stu_wallet = Wallet()
        self.jeff_wallet = Wallet()
        self.oliver_wallet = Wallet()
        self.archer_wallet = Wallet()

        self.founder_wallet = Wallet()
        self.node_wallet = Wallet()
        self.blocks = MockBlocks(
            num_of_blocks=1,
            founder_wallet=self.founder_wallet,
            initial_members={
                'masternodes': [
                    self.node_wallet.verifying_key
                ]
            }
        )
        self.genesis_block = self.blocks.get_block_by_index(index=0)

        self.threaded_nodes = []

        self.temp_storage_root = Path().cwd().joinpath('temp_network')
        if self.temp_storage_root.is_dir():
            shutil.rmtree(self.temp_storage_root)

    def tearDown(self):
        for tn in self.threaded_nodes:
            self.await_async_process(tn.stop)
        if self.temp_storage_root.is_dir():
            shutil.rmtree(self.temp_storage_root)

        try:
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.close()
        except RuntimeError:
            pass

    def create_node(self, index=0, metering=False):
        tn = create_a_node(
            node_wallet=self.node_wallet,
            genesis_block=self.genesis_block,
            index=index,
            temp_storage_root=self.temp_storage_root,
            metering=metering
        )
        tn.set_smart_contract_value(f'currency.balances:{self.stu_wallet.verifying_key}', value=1_000_000)
        self.threaded_nodes.append(tn)

        return tn

    def start_node(self, tn: ThreadedNode):
        tn.start()

        while not tn.node or not tn.node.started or not tn.node.network.running:
            self.await_async_process(asyncio.sleep, 1)

    def create_and_start_node(self, index=0, metering=False) -> ThreadedNode:
        tn = self.create_node(index=index, metering=metering)
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

        self.await_node_reaches_height(tn, 2)

        block = tn.blocks.get_block(v=tn.latest_block_height)

        self.assertIsNotNone(block)

        self.assertEqual(tx_amount, tn.get_smart_contract_value(f'currency.balances:{self.jeff_wallet.verifying_key}'))
        self.assertEqual(stu_balance_before - tx_amount, tn.get_smart_contract_value(f'currency.balances:{self.stu_wallet.verifying_key}'))
        self.assertEqual(2, tn.blocks.total_blocks())

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
            self.await_async_process(asyncio.sleep, 0.1)

        self.await_node_reaches_height(tn, 4)

        self.assertEqual(4, tn.blocks.total_blocks())

        self.assertEqual(stu_balance_before - tx_amount, tn.get_smart_contract_value(f'currency.balances:{self.stu_wallet.verifying_key}'))
        self.assertEqual(0, tn.get_smart_contract_value(f'currency.balances:{self.jeff_wallet.verifying_key}'))
        self.assertEqual(0, tn.get_smart_contract_value(f'currency.balances:{self.archer_wallet.verifying_key}'))
        self.assertEqual(tx_amount, tn.get_smart_contract_value(f'currency.balances:{self.oliver_wallet.verifying_key}'))


    def test_not_enough_stamps(self):
        tn = self.create_and_start_node(metering=True)

        stu_balance_before = tn.get_smart_contract_value(f'currency.balances:{self.stu_wallet.verifying_key}')

        tx_amount = 200.1

        tx_args = {
            'to': self.jeff_wallet.verifying_key,
            'wallet': self.stu_wallet,
            'amount': tx_amount,
            'processor': tn.wallet.verifying_key,
            'stamps': 17
        }

        tn.send_tx(json.dumps(get_new_currency_tx(**tx_args)).encode())

        self.await_node_reaches_height(tn, 2)

        block = tn.blocks.get_block(v=tn.latest_block_height)

        self.assertIsNotNone(block)

        stamp_cost = tn.get_smart_contract_value('stamp_cost.S:value')
        expected_balance = stu_balance_before - 17/stamp_cost
        actual_balance = tn.get_smart_contract_value(f'currency.balances:{self.stu_wallet.verifying_key}')
        self.assertEqual(expected_balance, actual_balance)
        self.assertIsNone(tn.get_cached_smart_contract_value(f'currency.balances:{self.jeff_wallet.verifying_key}'))
        self.assertEqual(2, tn.blocks.total_blocks())

