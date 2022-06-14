'''
    !!!! THESE TESTS ARE LONG AND COULD EACH TAKE A FEW MINUTES TO COMPLETE !!!!

    THROUGHPUT Test send all transactions AT ONCE and then wait for all nodes to process them and come to consensus
    After all node are in sync then the test are run to validate state etc.

'''

from contracting.db import encoder
from contracting.stdlib.bridge.decimal import ContractingDecimal
from lamden import contracts
from lamden.crypto.wallet import Wallet
from tests.integration.mock.local_node_network import LocalNodeNetwork
from unittest import TestCase
import asyncio
import json
import random

class TestMultiNode(TestCase):
    def setUp(self):
        self.local_node_network = LocalNodeNetwork(num_of_masternodes=1, num_of_delegates=1,
            genesis_path=contracts.__path__[0], delay={'base': 1, 'self': 1.5})
        for node in self.local_node_network.all_nodes:
            self.assertTrue(node.node_is_running)
            node.contract_driver.set_var(
                contract='currency',
                variable='balances',
                arguments=[self.local_node_network.founders_wallet.verifying_key],
                value=1000000
            )

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

    def add_node_and_fund_founder(self, node_type):
        node = self.local_node_network.add_masternode() if node_type == 'm' else self.local_node_network.add_delegate()
        node.contract_driver.set_var(
            contract='currency',
            variable='balances',
            arguments=[self.local_node_network.founders_wallet.verifying_key],
            value=1000000
        )

    def test_network_linear_tx_throughput_test_founder_to_new_wallets(self):
        # This test will transfer from the founder wallet to a bunch of new wallets and never the same wallet twice
        test_tracker = {}
        amount_of_transactions = 25

        # Send a bunch of transactions
        for i in range(amount_of_transactions):
            tx_info = self.local_node_network.send_tx_to_random_masternode(
                sender_wallet=self.local_node_network.founders_wallet,
                receiver_vk=Wallet().verifying_key
            )
            to = tx_info['payload']['kwargs']['to']
            test_tracker[to] = float(tx_info['payload']['kwargs']['amount']['__fixed__'])

        # wait till all nodes reach the required block height
        self.local_node_network.await_all_nodes_done_processing(block_height=amount_of_transactions)
        self.async_sleep(1)

        # All state values reflect the result of the processed transactions
        for key in test_tracker:
            expected_balance = json.loads(encoder.encode(ContractingDecimal(test_tracker[key])))
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
            self.assertEqual(amount_of_transactions, node.current_height)

        # All nodes arrived at the same block hash
        all_hashes = [node.current_hash for node in self.local_node_network.all_nodes]
        self.assertTrue(all([block_hash == all_hashes[0] for block_hash in all_hashes]))

    def test_network_one_receiver__throughput_test__founder_to_one_wallet_multiple_times(self):
        # This test will transfer from the founder wallet to a random selection of existing wallets so that balances
        # accumulate as the test goes on

        test_tracker = ContractingDecimal(0.0)
        receiver_wallet = Wallet()
        amount_of_transactions = 20

        # Send a bunch of transactions
        for i in range(amount_of_transactions):
            tx_info = self.local_node_network.send_tx_to_random_masternode(
                sender_wallet=self.local_node_network.founders_wallet,
                receiver_vk=receiver_wallet.verifying_key
            )

            test_tracker = test_tracker + ContractingDecimal(tx_info['payload']['kwargs']['amount']['__fixed__'])

        # wait till all nodes reach the required block height
        self.local_node_network.await_all_nodes_done_processing(block_height=amount_of_transactions)
        self.async_sleep(1)

        # All state values reflect the result of the processed transactions
        # Decode all tracker values from ContractingDecimal to string

        actual_balances = json.loads(encoder.encode(self.local_node_network.get_var_from_all(
            contract='currency',
            variable='balances',
            arguments=[receiver_wallet.verifying_key]
        )))
        expected_balance = json.loads(encoder.encode(test_tracker))
        print({'expected_balance': expected_balance})
        print({'actual_balances': actual_balances})

        for actual_balance in actual_balances:
            self.assertEqual(actual_balance, expected_balance)

        # All nodes are at the proper block height
        for node in self.local_node_network.all_nodes:
            self.assertEqual(amount_of_transactions, node.current_height)

        # All nodes arrived at the same block hash
        all_hashes = [node.current_hash for node in self.local_node_network.all_nodes]
        self.assertTrue(all([block_hash == all_hashes[0] for block_hash in all_hashes]))

    def template_network_mixed_receivers__founder_to_list_of_created_wallets(self, test_info):
        # This test will transfer from the founder wallet to a random selection of existing wallets so that balances
        # accumulate as the test goes on

        num_of_masternodes, num_of_delegates, num_of_receiver_wallets, amount_of_transactions = test_info
        for i in range(num_of_masternodes - 1):
            self.add_node_and_fund_founder('m')

        for i in range(num_of_delegates - 1):
            self.add_node_and_fund_founder('d')

        test_tracker = {}
        receiver_wallets = [Wallet() for i in range(num_of_receiver_wallets)]

        for i in range(amount_of_transactions):
            tx_info = self.local_node_network.send_tx_to_random_masternode(
                sender_wallet=self.local_node_network.founders_wallet,
                receiver_vk=random.choice(receiver_wallets).verifying_key
            )
            to = tx_info['payload']['kwargs']['to']
            amount = float(tx_info['payload']['kwargs']['amount']['__fixed__'])
            if test_tracker.get(to, None) is None:
                test_tracker[to] = amount
            else:
                test_tracker[to] += amount

        # wait till all nodes reach the required block height
        self.local_node_network.await_all_nodes_done_processing(block_height=amount_of_transactions)
        self.async_sleep(1)

        # All state values reflect the result of the processed transactions
        for key, value in test_tracker.items():
            expected_balance = json.loads(encoder.encode(ContractingDecimal(value)))
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
            self.assertEqual(amount_of_transactions, node.current_height)

        # All nodes arrived at the same block hash
        all_hashes = [node.current_hash for node in self.local_node_network.all_nodes]
        self.assertTrue(all([block_hash == all_hashes[0] for block_hash in all_hashes]))

    def test_network_mixed_receivers__throughput_test__low_nodes_low_txcount(self):
        # num_of_masternodes, num_of_delegates, num_of_receiver_wallets, amount_of_transactions = test_info
        test_info = [1, 1, 5, 20]

        self.template_network_mixed_receivers__founder_to_list_of_created_wallets(test_info)

    def test_network_mixed_receivers__throughput_test__low_nodes_high_tx_count(self):
        # num_of_masternodes, num_of_delegates, num_of_receiver_wallets, amount_of_transactions = test_info
        test_info = [1, 1, 5, 50]

        self.template_network_mixed_receivers__founder_to_list_of_created_wallets(test_info)

    def test_network_mixed_receivers__throughput_test__high_nodes_low_tx_count(self):
        # num_of_masternodes, num_of_delegates, num_of_receiver_wallets, amount_of_transactions = test_info
        test_info = [2, 2, 5, 20]

        self.template_network_mixed_receivers__founder_to_list_of_created_wallets(test_info)

    def test_network_mixed_receivers__throughput_test__high_nodes_high_tx_count(self):
        # num_of_masternodes, num_of_delegates, num_of_receiver_wallets, amount_of_transactions = test_info
        test_info = [2, 2, 5, 50]

        self.template_network_mixed_receivers__founder_to_list_of_created_wallets(test_info)

    def test_network_mixed_receivers__throughput_test__2_nodes_1_tx(self):
        # num_of_masternodes, num_of_delegates, num_of_receiver_wallets, amount_of_transactions = test_info
        test_info = [2, 1, 1, 1]

        self.template_network_mixed_receivers__founder_to_list_of_created_wallets(test_info)
