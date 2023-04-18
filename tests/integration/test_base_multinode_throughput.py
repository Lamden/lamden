'''
    !!!! THESE TESTS ARE LONG AND COULD EACH TAKE A FEW MINUTES TO COMPLETE !!!!

    THROUGHPUT Test send all transactions AT ONCE and then wait for all nodes to process them and come to consensus
    After all node are in sync then the test are run to validate state etc.

'''

from contracting.db import encoder
from contracting.stdlib.bridge.decimal import ContractingDecimal
from lamden.crypto.wallet import Wallet
from tests.integration.mock.local_node_network import LocalNodeNetwork
from unittest import TestCase
import asyncio
import json
import random
import time

class TestMultiNode(TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        self.test_tracker = {}
        self.amount_of_transactions = None
        self.local_node_network = None

        self.scenarios = {
            "high_nodes_low_tx_amount":{
                'num_of_masternodes': 10,
                'amount_of_transactions': 25
            },
            "low_nodes_high_tx_amount":{
                'num_of_masternodes': 4,
                'amount_of_transactions': 60
            }
        }

    def tearDown(self):
        self.await_async_process(self.local_node_network.stop_all_nodes)

        try:
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.close()
        except RuntimeError:
            pass

    def setup_nodes(self, num_of_masternodes, amount_of_transactions):
        test_start = time.time()

        self.local_node_network = LocalNodeNetwork(
            num_of_masternodes=num_of_masternodes
        )
        for node in self.local_node_network.all_nodes:
            self.assertTrue(node.node_is_running)
            node.set_smart_contract_value(
                key=f'currency.balances:{self.local_node_network.founders_wallet.verifying_key}',
                value=1000000
            )

        done_starting_networks = time.time()
        print(f"Took {done_starting_networks - test_start} seconds to start all networks.")

        self.amount_of_transactions = amount_of_transactions

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

    '''
        one_recipient test cases
        # These tests create a multi-node network which will process transactions which are sent at once.
        # Each transaction is a tx from the FOUNDATION wallet to the same receiver wallet.
        # After all transactions are done state will be tested to validate it is the same across all nodes.
    '''

    def test_network_one_recipient__throughput__high_nodes_low_tx_amount(self):
        self.setup_nodes(**self.scenarios["high_nodes_low_tx_amount"])
        self.one_recipient__throughput()

    def test_network_one_recipient__throughput__low_nodes_high_tx_amount(self):
        self.setup_nodes(**self.scenarios["low_nodes_high_tx_amount"])
        self.one_recipient__throughput()

    def one_recipient__throughput(self):
        receiver_wallet = Wallet()
        self.test_tracker[receiver_wallet.verifying_key] = ContractingDecimal(0)

        # Send a bunch of transactions
        for i in range(self.amount_of_transactions):
            tx_info = self.local_node_network.send_tx_to_random_masternode(
                sender_wallet=self.local_node_network.founders_wallet,
                receiver_vk=receiver_wallet.verifying_key
            )

            self.test_tracker[receiver_wallet.verifying_key] += ContractingDecimal(tx_info['payload']['kwargs']['amount']['__fixed__'])

        # wait till all nodes reach the required block height
        self.local_node_network.await_all_nodes_done_processing(block_height=self.amount_of_transactions + 1)

        # All state values reflect the result of the processed transactions
        expected_balance = json.loads(encoder.encode(self.test_tracker[receiver_wallet.verifying_key]))
        actual_balances = json.loads(encoder.encode(self.local_node_network.get_var_from_all(
            f'currency.balances:{receiver_wallet.verifying_key}'
        )))
        print({'expected_balance': expected_balance})
        print({'actual_balances': actual_balances})

        for actual_balance in actual_balances:
            if actual_balance != expected_balance:
                key = f'currency.balances:{receiver_wallet.verifying_key}'
                print(f'currency.balances:{receiver_wallet.verifying_key}')
            self.assertEqual(actual_balance, expected_balance)

        # All nodes are at the proper block height
        for tn in self.local_node_network.all_nodes:
            self.assertEqual(self.amount_of_transactions + 1, tn.node.blocks.total_blocks())

        # All nodes arrived at the same block hash
        all_hashes = [node.current_hash for node in self.local_node_network.all_nodes]
        self.assertTrue(all([block_hash == all_hashes[0] for block_hash in all_hashes]))

    '''
        mixed tx test cases
        # These tests create a multi-node network which will process transactions which are sent at once.
        # Each transaction is a tx from the FOUNDATION wallet to a new random wallet.
        # After all transactions are done state will be tested to validate it is the same across all nodes.
    '''

    def test_network_mixed_tx__throughput__high_nodes_low_tx_amount(self):
        self.setup_nodes(**self.scenarios["high_nodes_low_tx_amount"])
        self.mixed_tx__throughput()

    def test_network_mixed_tx__throughput___low_nodes_high_tx_amount(self):
        self.setup_nodes(**self.scenarios["low_nodes_high_tx_amount"])
        self.mixed_tx__throughput()

    def mixed_tx__throughput(self):
        # Send a bunch of transactions
        for i in range(self.amount_of_transactions):
            tx_info = self.local_node_network.send_tx_to_random_masternode(
                sender_wallet=self.local_node_network.founders_wallet,
                receiver_vk=Wallet().verifying_key
            )
            to = tx_info['payload']['kwargs']['to']
            self.test_tracker[to] = float(tx_info['payload']['kwargs']['amount']['__fixed__'])

        # wait till all nodes reach the required block height
        self.local_node_network.await_all_nodes_done_processing(block_height=self.amount_of_transactions + 1)

        # All state values reflect the result of the processed transactions
        for key, value in self.test_tracker.items():
            expected_balance = json.loads(encoder.encode(ContractingDecimal(value)))
            actual_balances = json.loads(encoder.encode(
                self.local_node_network.get_var_from_all(f'currency.balances:{key}')
            ))
            print({'expected_balance': expected_balance})
            print({'actual_balances': actual_balances})

            for actual_balance in actual_balances:
                if expected_balance != actual_balance:
                    print({'key': key})
                self.assertEqual(expected_balance, actual_balance)

        # All nodes are at the proper block height
        for tn in self.local_node_network.all_nodes:
            self.assertEqual(self.amount_of_transactions + 1, tn.node.blocks.total_blocks())

        # All nodes arrived at the same block hash
        all_hashes = [node.current_hash for node in self.local_node_network.all_nodes]
        self.assertTrue(all([block_hash == all_hashes[0] for block_hash in all_hashes]))

    '''
        mixed tx to set group of receivers test cases
        # These tests create a multi-node network which will process transactions which are sent at once.
        # Each transaction is a tx from the FOUNDATION wallet to a group of established wallets.
        # After all transactions are done state will be tested to validate it is the same across all nodes.
    '''

    def test_network_mixed_tx_set_group__throughput__high_nodes_low_tx_amount(self):
        self.setup_nodes(**self.scenarios["high_nodes_low_tx_amount"])
        self.mixed_tx_set_group__throughput()

    def test_network_mixed_tx_set_group__throughput__low_nodes_high_tx_amount(self):
        self.setup_nodes(**self.scenarios["low_nodes_high_tx_amount"])
        self.mixed_tx_set_group__throughput()

    def mixed_tx_set_group__throughput(self):
        receiver_wallets = [Wallet() for i in range(3)]

        # Send a bunch of transactions
        for i in range(self.amount_of_transactions):
            tx_info = self.local_node_network.send_tx_to_random_masternode(
                sender_wallet=self.local_node_network.founders_wallet,
                receiver_vk=random.choice(receiver_wallets).verifying_key
            )
            to = tx_info['payload']['kwargs']['to']
            amount = float(tx_info['payload']['kwargs']['amount']['__fixed__'])
            if self.test_tracker.get(to, None) is None:
                self.test_tracker[to] = amount
            else:
                self.test_tracker[to] += amount

        # wait till all nodes reach the required block height
        self.local_node_network.await_all_nodes_done_processing(block_height=self.amount_of_transactions + 1)

        # All state values reflect the result of the processed transactions
        for key, value in self.test_tracker.items():
            expected_balance = json.loads(encoder.encode(ContractingDecimal(value)))
            actual_balances = json.loads(encoder.encode(
                self.local_node_network.get_var_from_all(f'currency.balances:{key}')
            ))
            print({'expected_balance': expected_balance})
            print({'actual_balances': actual_balances})
            for actual_balance in actual_balances:
                if expected_balance != actual_balance:
                    print(expected_balance, actual_balance)
                self.assertEqual(expected_balance, actual_balance)

        # All nodes are at the proper block height
        for tn in self.local_node_network.all_nodes:
            self.assertEqual(self.amount_of_transactions + 1, tn.node.blocks.total_blocks())

        # All nodes arrived at the same block hash
        all_hashes = [node.current_hash for node in self.local_node_network.all_nodes]
        self.assertTrue(all([block_hash == all_hashes[0] for block_hash in all_hashes]))
