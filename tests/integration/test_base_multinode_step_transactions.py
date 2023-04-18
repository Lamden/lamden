'''
    !!!! THESE TESTS ARE LONG AND COULD EACH TAKE A FEW MINUTES TO COMPLETE !!!!

    STEP BY STEP TESTS

    These tests send transactions 1 at a time, waiting for each node to process and meet consensus before sending
    another. Each test case validates the state syncing of nodes after each tx is sent and then at the end

'''

from lamden.crypto.wallet import Wallet
from contracting.stdlib.bridge.decimal import ContractingDecimal
from contracting.db import encoder
import asyncio
import random
import json
import time
from unittest import TestCase

from tests.integration.mock.local_node_network import LocalNodeNetwork
from tests.integration.mock.mock_data_structures import MockBlocks
from lamden import contracts

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
            node.raw_driver.set(
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

    def validate_block_height_in_all_nodes(self, nodes, valid_height):
        all_heights = [node.blocks.total_blocks() for node in nodes]
        print({'valid_height': valid_height})
        print({'all_heights': all_heights})
        print(all([valid_height == height for height in all_heights]))
        self.assertTrue(all([valid_height == height for height in all_heights]))

    def validate_block_hash_in_all_nodes(self, nodes):
        all_hashes = [node.current_hash for node in nodes]
        print({'all_hashes': all_hashes})
        print(all([all_hashes[0] == block_hash for block_hash in all_hashes]))
        self.assertTrue(all([all_hashes[0] == block_hash for block_hash in all_hashes]))

    '''
        one_recipient test cases
        # This test creates a multi-node network which will process transactions one at a time. Each transaction
        # is a tx from the FOUNDATION wallet to the same receiver wallet.
        # I will test that all nodes come to the same block height after each transaction, before sending the next.
        # After all transactions are done state will be tested to validate it is the same across all nodes.
    '''

    def test_network_one_recipient__step_by_step__validate_node_state_inbetween__high_nodes_low_tx_amount(self):
        self.setup_nodes(**self.scenarios["high_nodes_low_tx_amount"])
        self.one_recipient__step_by_step__validate_node_state_inbetween()

    def test_network_one_recipient__step_by_step__validate_node_state_inbetween__low_nodes_high_tx_amount(self):
        self.setup_nodes(**self.scenarios["low_nodes_high_tx_amount"])
        self.one_recipient__step_by_step__validate_node_state_inbetween()

    def one_recipient__step_by_step__validate_node_state_inbetween(self):
        receiver_wallet = Wallet()

        # Send a bunch of transactions
        test_start_sending_transactions = time.time()
        for i in range(self.amount_of_transactions):
            test_start_sending_transaction = time.time()

            tx_info = self.local_node_network.send_tx_to_random_masternode(
                sender_wallet=self.local_node_network.founders_wallet,
                receiver_vk= receiver_wallet.verifying_key
            )
            to = tx_info['payload']['kwargs']['to']
            amount = float(tx_info['payload']['kwargs']['amount']['__fixed__'])

            if self.test_tracker.get(to, None) is None:
                self.test_tracker[to] = amount
            else:
                self.test_tracker[to] += amount

            # wait till all nodes reach the required block height
            self.local_node_network.await_all_nodes_done_processing(block_height=i+2)

            end_sending_transaction = time.time()
            print(f"Took {end_sending_transaction - test_start_sending_transaction} seconds to process tx {i + 1}.")

            self.validate_block_height_in_all_nodes(nodes=self.local_node_network.all_nodes, valid_height=i+2)
            self.validate_block_hash_in_all_nodes(nodes=self.local_node_network.all_nodes)

            # All state values reflect the result of the processed transaction
            expected_balance = json.loads(
                encoder.encode(ContractingDecimal(self.test_tracker[receiver_wallet.verifying_key])))
            actual_balances = json.loads(encoder.encode(self.local_node_network.get_var_from_all(
                key=f'currency.balances:{receiver_wallet.verifying_key}'
            )))
            print({'expected_balance': expected_balance})
            print({'actual_balances': actual_balances})

        print(f"Took {time.time() - test_start_sending_transactions } seconds to process ALL transactions.")

        # TODO INVESTIGATE: having multiple masternodes leads to incorrect balances
        for actual_balance in actual_balances:
            self.assertEqual(actual_balance, expected_balance)

        # All nodes are at the proper block height
        for node in self.local_node_network.all_nodes:
            self.assertEqual(self.amount_of_transactions + 1, node.blocks.total_blocks())

        # All nodes arrived at the same block hash
        all_hashes = [node.current_hash for node in self.local_node_network.all_nodes]
        self.assertTrue(all(block_hash == all_hashes[0] for block_hash in all_hashes))

    '''
        mixed tx test cases
        # This test creates a multi-node network which will process transactions one at a time. Each transaction
        # is a tx from the FOUNDATION wallet to a new random wallet.
        # I will test that all nodes come to the same block height after each transaction, before sending the next.
        # After all transactions are done state will be tested to validate it is the same across all nodes.
    '''

    def test_network_mixed_tx__step_by_step__validate_node_state_inbetween__high_nodes_low_tx_amount(self):
        self.setup_nodes(**self.scenarios["high_nodes_low_tx_amount"])
        self.network_mixed_tx__step_by_step__validate_node_state_inbetween()

    def test_network_mixed_tx__step_by_step__validate_node_state_inbetween___low_nodes_high_tx_amount(self):
        self.setup_nodes(**self.scenarios["low_nodes_high_tx_amount"])
        self.network_mixed_tx__step_by_step__validate_node_state_inbetween()

    def network_mixed_tx__step_by_step__validate_node_state_inbetween(self):

        # Send a bunch of transactions
        test_start_sending_transactions = time.time()

        for i in range(self.amount_of_transactions):
            test_start_sending_transaction = time.time()

            tx_info = self.local_node_network.send_tx_to_random_masternode(
                sender_wallet=self.local_node_network.founders_wallet,
                receiver_vk= Wallet().verifying_key
            )
            to = tx_info['payload']['kwargs']['to']
            amount = float(tx_info['payload']['kwargs']['amount']['__fixed__'])

            if self.test_tracker.get(to, None) is None:
                self.test_tracker[to] = amount
            else:
                self.test_tracker[to] += amount

            # wait till all nodes reach the required block height
            self.local_node_network.await_all_nodes_done_processing(block_height=i+2)
            end_sending_transaction = time.time()
            print(f"Took {end_sending_transaction - test_start_sending_transaction} seconds to process tx {i + 1}.")

            self.validate_block_height_in_all_nodes(nodes=self.local_node_network.all_nodes, valid_height=i+2)
            self.validate_block_hash_in_all_nodes(nodes=self.local_node_network.all_nodes)

            # All state values reflect the result of the processed transactions
            for key in self.test_tracker:
                expected_balance = json.loads(encoder.encode(ContractingDecimal(self.test_tracker[key])))
                actual_balances = json.loads(encoder.encode(self.local_node_network.get_var_from_all(
                    key=f'currency.balances:{key}'
                )))
                print({'expected_balance': expected_balance})
                print({'actual_balances': actual_balances})
                for actual_balance in actual_balances:
                    self.assertEqual(expected_balance, actual_balance)

        print(f"Took {time.time() - test_start_sending_transactions } seconds to process ALL transactions.")

        # All nodes are at the proper block height
        for node in self.local_node_network.all_nodes:
            self.assertEqual(self.amount_of_transactions + 1, node.blocks.total_blocks())

        # All nodes arrived at the same block hash
        all_hashes = [node.current_hash for node in self.local_node_network.all_nodes]
        self.assertTrue(all(block_hash == all_hashes[0] for block_hash in all_hashes))

    '''
        mixed tx to set group of receivers
        
        # This test creates a multi-node network which will process transactions one at a time. Each transaction
        # is a tx from the FOUNDATION wallet to a group of established wallets
        # I will test that all nodes come to the same block height after each transaction, before sending the next.
        # After all transactions are done state will be tested to validate it is the same across all nodes.

    '''

    def test_network_mixed_tx_set_group__step_by_step__validate_node_state_inbetween__high_nodes_low_tx_amount(self):
        self.setup_nodes(**self.scenarios["high_nodes_low_tx_amount"])
        self.network_mixed_tx_set_group__step_by_step__validate_node_state_inbetween()

    def test_network_mixed_tx_set_group__step_by_step__validate_node_state_inbetween__low_nodes_high_tx_amount(self):
        self.setup_nodes(**self.scenarios["low_nodes_high_tx_amount"])
        self.network_mixed_tx_set_group__step_by_step__validate_node_state_inbetween()

    def network_mixed_tx_set_group__step_by_step__validate_node_state_inbetween(self):
        receiver_wallets = [Wallet() for i in range(3)]

        # Send a bunch of transactions
        test_start_sending_transactions = time.time()
        for i in range(self.amount_of_transactions):
            test_start_sending_transaction = time.time()

            processor_node = random.choice(self.local_node_network.masternodes)
            # TODO: local_node_network.send_random_currency_transaction
            # sender_wallet, receiver_wallet, amount
            receiver_wallet = random.choice(receiver_wallets)
            tx_info = self.local_node_network.send_tx_to_random_masternode(
                sender_wallet=self.local_node_network.founders_wallet,
                receiver_vk= receiver_wallet.verifying_key
            )
            to = tx_info['payload']['kwargs']['to']
            amount = float(tx_info['payload']['kwargs']['amount']['__fixed__'])

            if self.test_tracker.get(to, None) is None:
                self.test_tracker[to] = amount
            else:
                self.test_tracker[to] += amount

            # wait till all nodes reach the required block height
            self.local_node_network.await_all_nodes_done_processing(block_height=i+2)
            end_sending_transaction = time.time()
            print(f"Took {end_sending_transaction - test_start_sending_transaction} seconds to process tx {i + 1}.")

            self.validate_block_height_in_all_nodes(nodes=self.local_node_network.all_nodes, valid_height=i+2)
            self.validate_block_hash_in_all_nodes(nodes=self.local_node_network.all_nodes)

            # All state values reflect the result of the processed transactions
            for key in self.test_tracker:
                expected_balance = json.loads(encoder.encode(ContractingDecimal(self.test_tracker[key])))
                actual_balances = json.loads(encoder.encode(self.local_node_network.get_var_from_all(
                    key=f'currency.balances:{key}'
                )))
                print({'expected_balance': expected_balance})
                print({'actual_balances': actual_balances})
                for actual_balance in actual_balances:
                    self.assertEqual(expected_balance, actual_balance)

            self.async_sleep(1)

        print(f"Took {time.time() - test_start_sending_transactions } seconds to process ALL transactions.")

        # All nodes are at the proper block height
        for node in self.local_node_network.all_nodes:
            self.assertEqual(self.amount_of_transactions + 1, node.blocks.total_blocks())

        # All nodes arrived at the same block hash
        all_hashes = [node.current_hash for node in self.local_node_network.all_nodes]
        self.assertTrue(all(block_hash == all_hashes[0] for block_hash in all_hashes))
