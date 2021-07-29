from tests.integration.mock import mocks_new
from lamden.nodes.filequeue import FileQueue

from lamden import router, storage, network, authentication
from lamden.crypto.wallet import Wallet
from lamden.crypto import transaction


from contracting.db.driver import InMemDriver, ContractDriver
from contracting.stdlib.bridge.decimal import ContractingDecimal
from contracting.client import ContractingClient
from contracting.db import encoder

import zmq.asyncio
import asyncio
import httpx
from random import randrange
import json
import time
import pprint

from unittest import TestCase


class TestMultiNode(TestCase):
    def setUp(self):
        self.fixture_directories = ['block_storage', 'file_queue', 'nonces', 'pending-nonces']
        mocks_new.create_fixture_directories(self.fixture_directories)

        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        print("\n")

    def tearDown(self):
        self.ctx.destroy()
        self.loop.close()
        mocks_new.remove_fixture_directories(self.fixture_directories)

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


    def test_network_mixed_tx__step_by_step__validate_node_state_inbetween(self):
        # This test create two networks.  network_1 is a single node network and network_2 is a multinode network
        # I will submit the same transaction to both networks and use network_1's output to validate the output on
        # network_2
        test_start = time.time()

        network_1 = mocks_new.MockNetwork(num_of_delegates=1, num_of_masternodes=2, ctx=self.ctx, metering=False)
        self.await_async_process(network_1.start)

        for node in network_1.all_nodes():
            self.assertTrue(node.obj.running)

        done_starting_networks = time.time()
        print(f"Took {done_starting_networks - test_start} seconds to start all networks.")

        # Send a bunch of transactions
        amount_of_transactions = 20

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
                timeout=15
            )
            end_sending_transaction = time.time()
            print(f"Took {end_sending_transaction - test_start_sending_transaction} seconds to process tx {i}.")

            self.async_sleep(2)

            self.validate_block_height_in_all_nodes(nodes=network_1.all_nodes(), valid_height=i+1)
            self.validate_block_hash_in_all_nodes(nodes=network_1.all_nodes())

        '''
        # All state values reflect the result of the processed transactions
        for key in test_tracker:
            balance = test_tracker[key]
            results = n.get_vars(
                contract='currency',
                variable='balances',
                arguments=[key]
            )

            self.assertTrue(balance == results[0])
            self.assertTrue(all(balance == results[0] for balance in results))

        # All nodes are at the proper block height
        for node in n.all_nodes():
            self.assertTrue(amount_of_transactions == node.obj.get_current_height())

        # All nodes arrived at the same block hash
        all_hashes = [node.obj.get_current_hash() for node in n.all_nodes()]
        self.assertTrue(all(block_hash == all_hashes[0] for block_hash in all_hashes))
        '''
