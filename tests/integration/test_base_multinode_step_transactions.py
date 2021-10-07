'''
    !!!! THESE TESTS ARE LONG AND COULD EACH TAKE A FEW MINUTES TO COMPLETE !!!!

    STEP BY STEP TESTS

    These tests send transactions 1 at a time, waiting for each node to process and meet consensus before sending
    another.  Each test case validates the state syncing of nodes after each tx is sent and then at the end

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


class TestMultiNode(TestCase):
    def setUp(self):
        self.fixture_directories = ['block_storage', 'file_queue', 'nonces', 'pending-nonces']
        create_directories.create_fixture_directories(self.fixture_directories)

        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        print("\n")

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()
        create_directories.remove_fixture_directories(self.fixture_directories)

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

    def send_transaction(self, node, tx):
        node.tx_queue.append(tx)

    def validate_block_height_in_all_nodes(self, nodes, valid_height):
        all_heights = [node.obj.get_current_height() for node in nodes]
        print({'valid_height': valid_height})
        print({'all_heights': all_heights})
        print(all([valid_height == height for height in all_heights]))
        self.assertTrue(all([valid_height == height for height in all_heights]))

    def validate_block_hash_in_all_nodes(self, nodes):
        all_hashes = [node.obj.get_current_hash() for node in nodes]
        print({'all_hashes': all_hashes})
        print(all([all_hashes[0] == block_hash for block_hash in all_hashes]))
        self.assertTrue(all([all_hashes[0] == block_hash for block_hash in all_hashes]))

    def test_network_one_recipient__step_by_step__validate_node_state_inbetween(self):
        # This test create a multi-node network which will process transactions one at a time. Each transaction
        # is a tx from the FOUNDATION wallet to the same receiver wallet.
        # I will test that all nodes come to the same block height after each transaction, before sending the next.
        # After all transactions are done state will be tested to validate it is the same across all nodes.

        test_start = time.time()

        network_1 = mocks_new.MockNetwork(
            num_of_delegates=6,
            num_of_masternodes=3,
            ctx=self.ctx,
            metering=False,
            delay={'base': 0.1, 'self': 0.1}
        )
        self.await_async_process(network_1.start)

        for node in network_1.all_nodes():
            self.assertTrue(node.obj.running)

        done_starting_networks = time.time()
        print(f"Took {done_starting_networks - test_start} seconds to start all networks.")

        # Send a bunch of transactions
        amount_of_transactions = 10
        receiver_wallet = Wallet()

        # Log the amounts of each transaction so we can verify state later
        test_tracker = {}

        test_start_sending_transactions = time.time()

        for i in range(amount_of_transactions):
            test_start_sending_transaction = time.time()

            tx_info = json.loads(network_1.send_random_currency_transaction(
                sender_wallet=mocks_new.TEST_FOUNDATION_WALLET,
                receiver_wallet=receiver_wallet
            ))

            to = tx_info['payload']['kwargs']['to']
            amount = ContractingDecimal(tx_info['payload']['kwargs']['amount']['__fixed__'])
            try:
                test_tracker[to] = test_tracker[to] + amount
            except KeyError:
                test_tracker[to] = amount

            # wait till all nodes reach the required block height
            mocks_new.await_all_nodes_done_processing(
                nodes=network_1.all_nodes(),
                block_height=i+1,
                timeout=0,
                sleep=1
            )
            end_sending_transaction = time.time()
            print(f"Took {end_sending_transaction - test_start_sending_transaction} seconds to process tx {i + 1}.")

            self.validate_block_height_in_all_nodes(nodes=network_1.all_nodes(), valid_height=i+1)
            self.validate_block_hash_in_all_nodes(nodes=network_1.all_nodes())
            pass

        print(f"Took {time.time() - test_start_sending_transactions } seconds to process ALL transactions.")

        # All state values reflect the result of the processed transactions
        for key in test_tracker:
            balance = json.loads(encoder.encode(test_tracker[key]))
            results = network_1.get_var_from_all(
                contract='currency',
                variable='balances',
                arguments=[key]
            )

            results = json.loads(encoder.encode(results))

            print({'results': results})
            print({'balance': balance})

            self.assertTrue(balance == results[0])
            self.assertTrue(all(balance == results[0] for balance in results))

        # All nodes are at the proper block height
        for node in network_1.all_nodes():
            self.assertTrue(amount_of_transactions == node.obj.get_current_height())

        # All nodes arrived at the same block hash
        all_hashes = [node.obj.get_current_hash() for node in network_1.all_nodes()]
        self.assertTrue(all(block_hash == all_hashes[0] for block_hash in all_hashes))

    def test_network_mixed_tx__step_by_step__validate_node_state_inbetween(self):
        # This test create a multi-node network which will process transactions one at a time. Each transaction
        # is a tx from the FOUNDATION wallet to a new random wallet.
        # I will test that all nodes come to the same block height after each transaction, before sending the next.
        # After all transactions are done state will be tested to validate it is the same across all nodes.

        test_start = time.time()

        network_1 = mocks_new.MockNetwork(
            num_of_delegates=6,
            num_of_masternodes=3,
            ctx=self.ctx,
            metering=False,
            delay={'base': 0.1, 'self': 0.1}
        )
        self.await_async_process(network_1.start)

        for node in network_1.all_nodes():
            self.assertTrue(node.obj.running)

        done_starting_networks = time.time()
        print(f"Took {done_starting_networks - test_start} seconds to start all networks.")

        # Send a bunch of transactions
        amount_of_transactions = 5

        # Log the amounts of each transaction so we can verify state later
        test_tracker = {}

        test_start_sending_transactions = time.time()
        for i in range(amount_of_transactions):
            test_start_sending_transaction = time.time()

            tx_info = json.loads(network_1.send_random_currency_transaction(sender_wallet=mocks_new.TEST_FOUNDATION_WALLET))

            to = tx_info['payload']['kwargs']['to']
            amount = tx_info['payload']['kwargs']['amount']
            test_tracker[to] = amount

            # wait till all nodes reach the required block height
            mocks_new.await_all_nodes_done_processing(
                nodes=network_1.all_nodes(),
                block_height=i+1,
                timeout=0
            )
            end_sending_transaction = time.time()
            print(f"Took {end_sending_transaction - test_start_sending_transaction} seconds to process tx {i + 1}.")

            self.validate_block_height_in_all_nodes(nodes=network_1.all_nodes(), valid_height=i+1)
            self.validate_block_hash_in_all_nodes(nodes=network_1.all_nodes())

        print(f"Took {time.time() - test_start_sending_transactions} seconds to process ALL transactions.")

        # All state values reflect the result of the processed transactions
        for key in test_tracker:
            balance = test_tracker[key]
            results = network_1.get_vars(
                contract='currency',
                variable='balances',
                arguments=[key]
            )

            self.assertTrue(balance == results[0])
            self.assertTrue(all(balance == results[0] for balance in results))

        # All nodes are at the proper block height
        for node in network_1.all_nodes():
            self.assertTrue(amount_of_transactions == node.obj.get_current_height())

        # All nodes arrived at the same block hash
        all_hashes = [node.obj.get_current_hash() for node in network_1.all_nodes()]
        self.assertTrue(all(block_hash == all_hashes[0] for block_hash in all_hashes))

    def test_network_mixed_tx_set_group_step_by_step__validate_node_state_inbetween(self):
        # This test create a multi-node network which will process transactions one at a time. Each transaction
        # is a tx from the FOUNDATION wallet to a group of established wallets
        # I will test that all nodes come to the same block height after each transaction, before sending the next.
        # After all transactions are done state will be tested to validate it is the same across all nodes.

        test_start = time.time()

        network_1 = mocks_new.MockNetwork(
            num_of_delegates=6,
            num_of_masternodes=3,
            ctx=self.ctx,
            metering=False,
            delay={'base': 0.1, 'self': 0.1}
        )
        self.await_async_process(network_1.start)

        for node in network_1.all_nodes():
            self.assertTrue(node.obj.running)

        done_starting_networks = time.time()
        print(f"Took {done_starting_networks - test_start} seconds to start all networks.")

        # Send a bunch of transactions
        amount_of_transactions = 20

        # Log the amounts of each transaction so we can verify state later
        test_tracker = {}

        receiver_wallets = [Wallet() for i in range(3)]

        test_start_sending_transactions = time.time()
        for i in range(amount_of_transactions):
            test_start_sending_transaction = time.time()

            tx_info = json.loads(network_1.send_random_currency_transaction(
                sender_wallet=mocks_new.TEST_FOUNDATION_WALLET,
                receiver_wallet=random.choice(receiver_wallets)
            ))

            to = tx_info['payload']['kwargs']['to']
            amount = tx_info['payload']['kwargs']['amount']['__fixed__']

            if test_tracker.get(to, None) is None:
                test_tracker[to] = ContractingDecimal(amount)
            else:
                test_tracker[to] = test_tracker[to] + ContractingDecimal(amount)

            # wait till all nodes reach the required block height
            mocks_new.await_all_nodes_done_processing(
                nodes=network_1.all_nodes(),
                block_height=i+1,
                timeout=0
            )
            end_sending_transaction = time.time()
            print(f"Took {end_sending_transaction - test_start_sending_transaction} seconds to process tx {i + 1}.")

            self.validate_block_height_in_all_nodes(nodes=network_1.all_nodes(), valid_height=i+1)
            self.validate_block_hash_in_all_nodes(nodes=network_1.all_nodes())

        print(f"Took {time.time() - test_start_sending_transactions} seconds to process ALL transactions.")

        # All state values reflect the result of the processed transactions
        for key in test_tracker:
            balance = str(test_tracker[key])
            results = network_1.get_vars(
                contract='currency',
                variable='balances',
                arguments=[key]
            )

            self.assertTrue(balance == results[0]['__fixed__'])
            self.assertTrue(all(balance['__fixed__'] == results[0]['__fixed__'] for balance in results))

        # All nodes are at the proper block height
        for node in network_1.all_nodes():
            self.assertTrue(amount_of_transactions == node.obj.get_current_height())

        # All nodes arrived at the same block hash
        all_hashes = [node.obj.get_current_hash() for node in network_1.all_nodes()]
        self.assertTrue(all(block_hash == all_hashes[0] for block_hash in all_hashes))