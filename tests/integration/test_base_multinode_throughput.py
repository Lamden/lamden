'''
    !!!! THESE TESTS ARE LONG AND COULD EACH TAKE A FEW MINUTES TO COMPLETE !!!!

    THROUGHPUT Test send all transactions AT ONCE and then wait for all nodes to process them and come to consensus
    After all node are in sync then the test are run to validate state etc.

'''

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
import os
import shutil

from unittest import TestCase


class TestMultiNode(TestCase):
    def setUp(self):
        self.fixture_directories = ['block_storage', 'file_queue', 'nonces', 'pending-nonces']
        mocks_new.create_fixture_directories(self.fixture_directories)

        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

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

    def test_mock_network_init_makes_correct_number_of_nodes(self):
        n = mocks_new.MockNetwork(num_of_delegates=1, num_of_masternodes=1, ctx=self.ctx, metering=False)
        self.assertEqual(len(n.masternodes), 1)
        self.assertEqual(len(n.delegates), 1)

    def test_mock_network_init_makes_correct_number_of_nodes_many_nodes(self):
        n = mocks_new.MockNetwork(num_of_delegates=123, num_of_masternodes=143, ctx=self.ctx, metering=False)
        self.assertEqual(len(n.masternodes), 143)
        self.assertEqual(len(n.delegates), 123)

    def test_mock_network_init_creates_correct_bootnodes(self):
        # 2 mn, 3 delegate
        expected_ips = [
            'tcp://127.0.0.1:18000',
            'tcp://127.0.0.1:18001',
            'tcp://127.0.0.1:18002',
            'tcp://127.0.0.1:18003',
            'tcp://127.0.0.1:18004',
            'tcp://127.0.0.1:18005',
            'tcp://127.0.0.1:18006',
            'tcp://127.0.0.1:18007',
            'tcp://127.0.0.1:18008'
        ]

        n = mocks_new.MockNetwork(num_of_masternodes=3, num_of_delegates=6, ctx=self.ctx)

        self.assertEqual(n.masternodes[0].tcp, expected_ips[0])
        self.assertEqual(n.masternodes[1].tcp, expected_ips[1])
        self.assertEqual(n.masternodes[2].tcp, expected_ips[2])
        self.assertEqual(n.delegates[0].tcp, expected_ips[3])
        self.assertEqual(n.delegates[1].tcp, expected_ips[4])
        self.assertEqual(n.delegates[2].tcp, expected_ips[5])
        self.assertEqual(n.delegates[3].tcp, expected_ips[6])
        self.assertEqual(n.delegates[4].tcp, expected_ips[7])
        self.assertEqual(n.delegates[5].tcp, expected_ips[8])

    def test_startup_with_manual_node_creation_and_single_block_works(self):
        m = mocks_new.MockMaster(ctx=self.ctx, index=1, metering=False)
        d = mocks_new.MockDelegate(ctx=self.ctx, index=2, metering=False)

        bootnodes = {
            m.wallet.verifying_key: m.tcp,
            d.wallet.verifying_key: d.tcp
        }

        constitution = {
            'masternodes': [m.wallet.verifying_key],
            'delegates': [d.wallet.verifying_key]
        }

        m.set_start_variables(bootnodes, constitution)
        d.set_start_variables(bootnodes, constitution)

        self.await_async_process(m.start)
        self.await_async_process(d.start)

        self.assertTrue(m.obj.running)
        self.assertTrue(d.obj.running)

        sender = Wallet()
        tx_amount = 1_000_000

        tx_1 = transaction.build_transaction(
            wallet=mocks_new.TEST_FOUNDATION_WALLET,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': tx_amount,
                'to': sender.verifying_key
            },
            stamps=10000,
            nonce=0,
            processor=m.wallet.verifying_key
        )

        self.send_transaction(node=m.obj, tx=tx_1.encode())
        self.async_sleep(1)

        mbal = m.driver.get_var(contract='currency', variable='balances', arguments=[sender.verifying_key])
        dbal = d.driver.get_var(contract='currency', variable='balances', arguments=[sender.verifying_key])

        self.assertEqual(mbal, tx_amount)
        self.assertEqual(dbal, tx_amount)

    def test_network_linear_tx_throughput_test_founder_to_new_wallets(self):
        # This test will transfer from the founder wallet to a bunch of new wallets and never the same wallet twice
        n = mocks_new.MockNetwork(num_of_delegates=6, num_of_masternodes=3, ctx=self.ctx, metering=False)
        self.await_async_process(n.start)

        for node in n.all_nodes():
            self.assertTrue(node.obj.running)

        test_tracker = {}

        # Send a bunch of transactions
        amount_of_transactions = 2

        for i in range(amount_of_transactions):
            tx_info = json.loads(n.send_random_currency_transaction(sender_wallet=mocks_new.TEST_FOUNDATION_WALLET))
            to = tx_info['payload']['kwargs']['to']
            amount = tx_info['payload']['kwargs']['amount']
            test_tracker[to] = amount

        # wait till all nodes reach the required block height
        mocks_new.await_all_nodes_done_processing(nodes=n.all_nodes(), block_height=amount_of_transactions, timeout=25)
        self.async_sleep(1)

        # All state values reflect the result of the processed transactions
        for key in test_tracker:
            balance = test_tracker[key]
            results = n.get_vars(
                contract='currency',
                variable='balances',
                arguments=[key]
            )

            self.assertTrue(balance == results[0])
            self.assertTrue(all([balance == results[0] for balance in results]))

        # All nodes are at the proper block height
        for node in n.all_nodes():
            self.assertTrue(amount_of_transactions == node.obj.get_consensus_height())

        # All nodes arrived at the same block hash
        all_hashes = [node.obj.get_consensus_hash() for node in n.all_nodes()]
        self.assertTrue(all([block_hash == all_hashes[0] for block_hash in all_hashes]))

    def test_network_one_receiver__throughput_test__founder_to_one_wallet_multiple_times(self):
        # This test will transfer from the founder wallet to a random selection of existing wallets so that balances
        # accumulate as the test goes on

        n = mocks_new.MockNetwork(num_of_delegates=6, num_of_masternodes=3, ctx=self.ctx, metering=False)
        self.await_async_process(n.start)

        for node in n.all_nodes():
            self.assertTrue(node.obj.running)

        test_tracker = {}

        num_of_receivers = 10
        receiver_wallet = Wallet()

        # Send a bunch of transactions
        amount_of_transactions = 5

        for i in range(amount_of_transactions):
            tx_info = json.loads(n.send_random_currency_transaction(
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
        mocks_new.await_all_nodes_done_processing(nodes=n.all_nodes(), block_height=amount_of_transactions, timeout=120)
        self.async_sleep(1)

        # All state values reflect the result of the processed transactions
        # Decode all tracker values from ContractingDecimal to string
        for key in test_tracker:
            test_tracker[key] = json.loads(encoder.encode(test_tracker[key]))

        for key in test_tracker:
            balance = json.loads(encoder.encode(test_tracker[key]))
            results = n.get_vars(
                contract='currency',
                variable='balances',
                arguments=[key]
            )

            results = json.loads(encoder.encode(results))

            print({'results': results})
            print({'balance': balance})

            self.assertTrue(balance == results[0])
            self.assertTrue(all([balance == results[0] for balance in results]))

        # All nodes are at the proper block height
        for node in n.all_nodes():
            print(f'{node.obj.upgrade_manager.node_type}-{node.index}')
            print(f'block height: {node.obj.get_consensus_height()} hash: {node.obj.get_consensus_hash()}')
            self.assertTrue(amount_of_transactions == node.obj.get_consensus_height())

        # All nodes arrived at the same block hash
        all_hashes = [node.obj.get_consensus_hash() for node in n.all_nodes()]
        for block_hash in all_hashes:
            print(block_hash)
        for node in n.all_nodes():
            print(node.obj.get_consensus_height())
        self.assertTrue(all([block_hash == all_hashes[0] for block_hash in all_hashes]))

    def test_network_mixed_receivers__throughput_test__founder_to_list_of_created_wallets(self):
        # This test will transfer from the founder wallet to a random selection of existing wallets so that balances
        # accumulate as the test goes on
        delay = {'base': 0.1, 'self': 0.5}
        n = mocks_new.MockNetwork(num_of_delegates=2, num_of_masternodes=3, ctx=self.ctx, metering=False, delay=delay)
        self.await_async_process(n.start)

        for node in n.all_nodes():
            self.assertTrue(node.obj.running)

        test_tracker = {}

        num_of_receivers = 6
        receiver_wallets = [Wallet() for i in range(num_of_receivers)]

        # Send a bunch of transactions
        amount_of_transactions = 6

        for i in range(amount_of_transactions):
            tx_info = json.loads(n.send_random_currency_transaction(
                sender_wallet=mocks_new.TEST_FOUNDATION_WALLET,
                receiver_wallet=receiver_wallets[randrange(0, num_of_receivers)]
            ))
            to = tx_info['payload']['kwargs']['to']
            amount = tx_info['payload']['kwargs']['amount']['__fixed__']
            if test_tracker.get(to) is None:
                test_tracker[to] = ContractingDecimal(amount)
            else:
                test_tracker[to] = test_tracker[to] + ContractingDecimal(amount)

        # wait till all nodes reach the required block height
        mocks_new.await_all_nodes_done_processing(nodes=n.all_nodes(), block_height=amount_of_transactions, timeout=60)
        self.async_sleep(1)

        # All state values reflect the result of the processed transactions
        # Decode all tracker values from ContractingDecimal to string
        for key in test_tracker:
            test_tracker[key] = json.loads(encoder.encode(test_tracker[key]))

        for key in test_tracker:
            balance = test_tracker[key]
            results = n.get_vars(
                contract='currency',
                variable='balances',
                arguments=[key]
            )

            self.assertTrue(balance == results[0])
            self.assertTrue(all([balance == results[0] for balance in results]))

        # All nodes are at the proper block height
        for node in n.all_nodes():
            print(f'{node.obj.upgrade_manager.node_type}-{node.index}')
            print(f'block height: {node.obj.get_consensus_height()} hash: {node.obj.get_consensus_height()}')
            self.assertTrue(amount_of_transactions == node.obj.get_consensus_height())

        # All nodes arrived at the same block hash
        all_hashes = [node.obj.get_consensus_height() for node in n.all_nodes()]
        for block_hash in all_hashes:
            print(block_hash)
        for node in n.all_nodes():
            print(node.obj.get_consensus_height())
        self.assertTrue(all([block_hash == all_hashes[0] for block_hash in all_hashes]))