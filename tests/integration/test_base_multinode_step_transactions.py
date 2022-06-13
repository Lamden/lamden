'''
    !!!! THESE TESTS ARE LONG AND COULD EACH TAKE A FEW MINUTES TO COMPLETE !!!!

    STEP BY STEP TESTS

    These tests send transactions 1 at a time, waiting for each node to process and meet consensus before sending
    another. Each test case validates the state syncing of nodes after each tx is sent and then at the end

'''

from tests.integration.mock import mocks_new, create_directories
from lamden.nodes.filequeue import FileQueue

from lamden import router, storage, network, authentication
from lamden.crypto.wallet import Wallet
from lamden.crypto import transaction
from contracting.stdlib.bridge.decimal import ContractingDecimal
from contracting.db.driver import InMemDriver, ContractDriver
from contracting.client import ContractingClient
from contracting.db import encoder

import zmq.asyncio
import asyncio
import random
import httpx
from random import randrange
import json
import time
import pprint

from unittest import TestCase

from tests.integration.mock.local_node_network import LocalNodeNetwork
from lamden import contracts
from tests.unit.helpers.mock_transactions import get_new_currency_tx

class TestMultiNode(TestCase):
    def setUp(self):
        test_start = time.time()

        self.local_node_network = LocalNodeNetwork(num_of_masternodes=1, num_of_delegates=1, genesis_path=contracts.__path__[0])
        for node in self.local_node_network.all_nodes:
            self.assertTrue(node.node_is_running)
            node.contract_driver.set_var(
                contract='currency',
                variable='balances',
                arguments=[self.local_node_network.founders_wallet.verifying_key],
                value=1000000
            )

        done_starting_networks = time.time()
        print(f"Took {done_starting_networks - test_start} seconds to start all networks.")

        self.amount_of_transactions = 2
        self.test_tracker = {}

    def tearDown(self):
        self.await_async_process(self.local_node_network.stop_all_nodes)

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
        all_heights = [node.current_height for node in nodes]
        print({'valid_height': valid_height})
        print({'all_heights': all_heights})
        print(all([valid_height == height for height in all_heights]))
        self.assertTrue(all([valid_height == height for height in all_heights]))

    def validate_block_hash_in_all_nodes(self, nodes):
        all_hashes = [node.current_hash for node in nodes]
        print({'all_hashes': all_hashes})
        print(all([all_hashes[0] == block_hash for block_hash in all_hashes]))
        self.assertTrue(all([all_hashes[0] == block_hash for block_hash in all_hashes]))

    def test_network_one_recipient__step_by_step__validate_node_state_inbetween(self):
        # This test create a multi-node network which will process transactions one at a time. Each transaction
        # is a tx from the FOUNDATION wallet to the same receiver wallet.
        # I will test that all nodes come to the same block height after each transaction, before sending the next.
        # After all transactions are done state will be tested to validate it is the same across all nodes.

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
            self.local_node_network.await_all_nodes_done_processing(block_height=i+1)

            end_sending_transaction = time.time()
            print(f"Took {end_sending_transaction - test_start_sending_transaction} seconds to process tx {i + 1}.")

            self.validate_block_height_in_all_nodes(nodes=self.local_node_network.all_nodes, valid_height=i+1)
            self.validate_block_hash_in_all_nodes(nodes=self.local_node_network.all_nodes)

        print(f"Took {time.time() - test_start_sending_transactions } seconds to process ALL transactions.")

        # All state values reflect the result of the processed transactions
        expected_balance = json.loads(encoder.encode(ContractingDecimal(self.test_tracker[receiver_wallet.verifying_key])))
        actual_balances = json.loads(encoder.encode(self.local_node_network.get_var_from_all(
            contract='currency',
            variable='balances',
            arguments=[receiver_wallet.verifying_key]
        )))

        print({'expected_balance': expected_balance})
        print({'actual_balances': actual_balances})

        # TODO INVESTIGATE: having multiple masternodes leads to incorrect balances
        for actual_balance in actual_balances:
            self.assertEqual(actual_balance, expected_balance)

        # All nodes are at the proper block height
        for node in self.local_node_network.all_nodes:
            self.assertEqual(self.amount_of_transactions, node.current_height)

        # All nodes arrived at the same block hash
        all_hashes = [node.current_hash for node in self.local_node_network.all_nodes]
        self.assertTrue(all(block_hash == all_hashes[0] for block_hash in all_hashes))

    def test_network_mixed_tx__step_by_step__validate_node_state_inbetween(self):
        # This test create a multi-node network which will process transactions one at a time. Each transaction
        # is a tx from the FOUNDATION wallet to a new random wallet.
        # I will test that all nodes come to the same block height after each transaction, before sending the next.
        # After all transactions are done state will be tested to validate it is the same across all nodes.

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
            self.local_node_network.await_all_nodes_done_processing(block_height=i+1)
            end_sending_transaction = time.time()
            print(f"Took {end_sending_transaction - test_start_sending_transaction} seconds to process tx {i + 1}.")

            self.validate_block_height_in_all_nodes(nodes=self.local_node_network.all_nodes, valid_height=i+1)
            self.validate_block_hash_in_all_nodes(nodes=self.local_node_network.all_nodes)

        print(f"Took {time.time() - test_start_sending_transactions } seconds to process ALL transactions.")

        # All state values reflect the result of the processed transactions
        for key in self.test_tracker:
            expected_balance = json.loads(encoder.encode(ContractingDecimal(self.test_tracker[key])))
            actual_balances = json.loads(encoder.encode(self.local_node_network.get_var_from_all(
                contract='currency',
                variable='balances',
                arguments=[key]
            )))
            print({'expected_balance': expected_balance})
            print({'actual_balances': actual_balances})
            for actual_balance in actual_balances:
                self.assertEqual(expected_balance, actual_balance)

        # All nodes are at the proper block height
        for node in self.local_node_network.all_nodes:
            self.assertEqual(self.amount_of_transactions, node.current_height)

        # All nodes arrived at the same block hash
        all_hashes = [node.current_hash for node in self.local_node_network.all_nodes]
        self.assertTrue(all(block_hash == all_hashes[0] for block_hash in all_hashes))

    def test_network_mixed_tx_set_group_step_by_step__validate_node_state_inbetween(self):
        # This test create a multi-node network which will process transactions one at a time. Each transaction
        # is a tx from the FOUNDATION wallet to a group of established wallets
        # I will test that all nodes come to the same block height after each transaction, before sending the next.
        # After all transactions are done state will be tested to validate it is the same across all nodes.

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
            self.local_node_network.await_all_nodes_done_processing(block_height=i+1)
            end_sending_transaction = time.time()
            print(f"Took {end_sending_transaction - test_start_sending_transaction} seconds to process tx {i + 1}.")

            self.validate_block_height_in_all_nodes(nodes=self.local_node_network.all_nodes, valid_height=i+1)
            self.validate_block_hash_in_all_nodes(nodes=self.local_node_network.all_nodes)

        print(f"Took {time.time() - test_start_sending_transactions } seconds to process ALL transactions.")

        # All state values reflect the result of the processed transactions
        for key in self.test_tracker:
            expected_balance = json.loads(encoder.encode(ContractingDecimal(self.test_tracker[key])))
            actual_balances = json.loads(encoder.encode(self.local_node_network.get_var_from_all(
                contract='currency',
                variable='balances',
                arguments=[key]
            )))
            print({'expected_balance': expected_balance})
            print({'actual_balances': actual_balances})
            for actual_balance in actual_balances:
                self.assertEqual(expected_balance, actual_balance)

        # All nodes are at the proper block height
        for node in self.local_node_network.all_nodes:
            self.assertEqual(self.amount_of_transactions, node.current_height)

        # All nodes arrived at the same block hash
        all_hashes = [node.current_hash for node in self.local_node_network.all_nodes]
        self.assertTrue(all(block_hash == all_hashes[0] for block_hash in all_hashes))
