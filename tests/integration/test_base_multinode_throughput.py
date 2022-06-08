'''
    !!!! THESE TESTS ARE LONG AND COULD EACH TAKE A FEW MINUTES TO COMPLETE !!!!

    THROUGHPUT Test send all transactions AT ONCE and then wait for all nodes to process them and come to consensus
    After all node are in sync then the test are run to validate state etc.

'''

from tests.integration.mock import mocks_new

from lamden.crypto.wallet import Wallet
from lamden.crypto import transaction

from contracting.stdlib.bridge.decimal import ContractingDecimal
from contracting.db import encoder

import zmq.asyncio
import asyncio
from random import randrange
import json


from unittest import TestCase


class TestMultiNode(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.n = None

    def tearDown(self):
        if self.n:
            for node in self.n.nodes:
                if node.started:
                    self.await_async_process(node.obj.stop)

        self.ctx.destroy()
        self.loop.close()

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

    def test_startup_with_manual_node_creation_and_single_block_works(self):
        m = mocks_new.MockMaster(ctx=self.ctx, index=1, metering=False)
        d = mocks_new.MockDelegate(ctx=self.ctx, index=2, metering=False)

        founder_waller = Wallet(seed=mocks_new.MOCK_FOUNDER_SK)

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
            wallet=founder_waller,
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

        self.await_async_process(m.stop)
        self.await_async_process(d.stop)

    def test_network_linear_tx_throughput_test_founder_to_new_wallets(self):
        # This test will transfer from the founder wallet to a bunch of new wallets and never the same wallet twice
        self.n = mocks_new.MockNetwork(num_of_delegates=6, num_of_masternodes=3, ctx=self.ctx, metering=False)
        self.await_async_process(self.n.start)

        for node in self.n.all_nodes():
            self.assertTrue(node.obj.running)

        test_tracker = {}

        # Send a bunch of transactions
        amount_of_transactions = 25

        for i in range(amount_of_transactions):
            tx_info = json.loads(self.n.send_random_currency_transaction(sender_wallet=self.n.founder_wallet))
            to = tx_info['payload']['kwargs']['to']
            amount = tx_info['payload']['kwargs']['amount']
            test_tracker[to] = amount

        # wait till all nodes reach the required block height
        mocks_new.await_all_nodes_done_processing(nodes=self.n.all_nodes(), block_height=amount_of_transactions, timeout=30)
        self.async_sleep(1)

        # All state values reflect the result of the processed transactions
        for key in test_tracker:
            balance = test_tracker[key]
            results = self.n.get_vars(
                contract='currency',
                variable='balances',
                arguments=[key]
            )

            self.assertTrue(balance == results[0])
            self.assertTrue(all([balance == results[0] for balance in results]))

        # All nodes are at the proper block height
        for node in self.n.all_nodes():
            self.assertTrue(amount_of_transactions == node.obj.get_current_height())

        # All nodes arrived at the same block hash
        all_hashes = [node.obj.get_current_hash() for node in self.n.all_nodes()]
        self.assertTrue(all([block_hash == all_hashes[0] for block_hash in all_hashes]))

    def test_network_one_receiver__throughput_test__founder_to_one_wallet_multiple_times(self):
        # This test will transfer from the founder wallet to a random selection of existing wallets so that balances
        # accumulate as the test goes on
        delay = {'base': 1, 'self': 1.5}
        self.n = mocks_new.MockNetwork(num_of_delegates=2, num_of_masternodes=2, ctx=self.ctx, metering=False, delay=delay)
        self.await_async_process(self.n.start)

        for node in self.n.all_nodes():
            self.assertTrue(node.obj.running)

        test_tracker = ContractingDecimal(0.0)

        receiver_wallet = Wallet()

        # Send a bunch of transactions
        amount_of_transactions = 20
        for i in range(amount_of_transactions):
            tx_info = json.loads(self.n.send_random_currency_transaction(
                sender_wallet=self.n.founder_wallet,
                receiver_wallet=receiver_wallet
            ))

            test_tracker = test_tracker + ContractingDecimal(tx_info['payload']['kwargs']['amount']['__fixed__'])

        # wait till all nodes reach the required block height
        mocks_new.await_all_nodes_done_processing(nodes=self.n.all_nodes(), block_height=amount_of_transactions, timeout=0)
        self.async_sleep(1)

        # All state values reflect the result of the processed transactions
        # Decode all tracker values from ContractingDecimal to string

        all_node_results = self.n.get_vars(
            contract='currency',
            variable='balances',
            arguments=[receiver_wallet.verifying_key]
        )

        all_node_results = json.loads(encoder.encode(all_node_results))
        balance = json.loads(encoder.encode(test_tracker))

        if (balance != all_node_results[0]):
            pass

        if all([balance == all_node_results[0] for balance in all_node_results]) == False:
            pass

        self.assertTrue(balance == all_node_results[0])
        self.assertTrue(all([balance == all_node_results[0] for balance in all_node_results]))

        # All nodes are at the proper block height
        for node in self.n.all_nodes():
            print(f'{node.obj.upgrade_manager.node_type}-{node.index}')
            print(f'block height: {node.obj.get_current_hash()} hash: {node.obj.get_current_hash()}')
            self.assertTrue(amount_of_transactions == node.obj.get_current_height())

        # All nodes arrived at the same block hash
        all_hashes = [node.obj.get_current_hash() for node in self.n.all_nodes()]
        for block_hash in all_hashes:
            print(block_hash)
        for node in self.n.all_nodes():
            print(node.obj.get_current_height())
        self.assertTrue(all([block_hash == all_hashes[0] for block_hash in all_hashes]))


    def template_network_mixed_receivers__founder_to_list_of_created_wallets(self, test_info):
        num_of_masternodes, num_of_delegates, num_of_receiver_wallets, amount_of_transactions, delay = test_info
        # This test will transfer from the founder wallet to a random selection of existing wallets so that balances
        # accumulate as the test goes on

        self.n = mocks_new.MockNetwork(
            num_of_delegates=num_of_delegates,
            num_of_masternodes=num_of_masternodes,
            ctx=self.ctx,
            metering=False,
            delay=delay
        )
        self.await_async_process(self.n.start)

        for node in self.n.all_nodes():
            self.assertTrue(node.obj.running)

        wallet_tracker = []

        receiver_wallets = [Wallet() for i in range(num_of_receiver_wallets)]

        for i in range(amount_of_transactions):
            tx_info = json.loads(self.n.send_random_currency_transaction(
                sender_wallet=self.n.founder_wallet,
                receiver_wallet=receiver_wallets[randrange(0, num_of_receiver_wallets)]
            ))

            to = tx_info['payload']['kwargs']['to']

            if to not in wallet_tracker:
                wallet_tracker.append(to)

        # wait till all nodes reach the required block height
        mocks_new.await_all_nodes_done_processing(nodes=self.n.all_nodes(), block_height=amount_of_transactions, timeout=0)
        self.async_sleep(1)

        # All state values reflect the result of the processed transactions
        all_node_results = {}
        for wallet in wallet_tracker:
            all_node_results[wallet] = self.n.get_vars(
                contract='currency',
                variable='balances',
                arguments=[wallet]
            )

        for key in all_node_results:
            # self.assertTrue(balance == all_node_results[key][0])
            self.assertTrue(all([balance == all_node_results[key][0] for balance in all_node_results[key]]))


        validation_history = self.n.masternodes[0].obj.validation_queue.validation_results_history

        all_hlcs = [[k for k in item.keys()][0] for item in validation_history]
        all_hlcs.sort()

        test_tracker = {}
        for hlc in all_hlcs:
            for result in validation_history:
                if result.get(hlc):
                    result_history = result[hlc][1]

            consensus_solution = result_history['last_check_info']['solution']
            processed_results = result_history['result_lookup'][consensus_solution]

            tx_result = processed_results.get('tx_result')

            for state_change in tx_result['state']:
                raw_key = state_change.get('key')
                key_split = raw_key.split(":")
                key = key_split[1]

                try:
                    value = state_change['value'].get('__fixed__')
                except Exception:
                    value = str(state_change.get('value'))

                test_tracker[key] = value

        for key in test_tracker:
            if all_node_results.get(key):
                self.assertEqual(all_node_results[key][0]['__fixed__'], test_tracker[key])

        # All nodes are at the proper block height
        for node in self.n.all_nodes():
            print(f'{node.obj.upgrade_manager.node_type}-{node.index}')
            print(f'block height: {node.obj.get_current_height()} hash: {node.obj.get_current_hash()}')
            self.assertTrue(amount_of_transactions == node.obj.get_current_height())

        # All nodes arrived at the same block hash
        all_hashes = [node.obj.get_current_height() for node in self.n.all_nodes()]
        for block_hash in all_hashes:
            print(block_hash)
        for node in self.n.all_nodes():
            print(node.obj.get_current_height())
        self.assertTrue(all([block_hash == all_hashes[0] for block_hash in all_hashes]))

    def test_network_mixed_receivers__throughput_test__low_nodes_low_txcount(self):
        # num_of_masternodes, num_of_delegates, num_of_receiver_wallets, amount_of_transactions, delay = test_info
        test_info = [1, 1, 5, 20, {'base': 1, 'self': 1.5}]

        self.template_network_mixed_receivers__founder_to_list_of_created_wallets(test_info)

    def test_network_mixed_receivers__throughput_test__low_nodes_high_tx_count(self):
        # num_of_masternodes, num_of_delegates, num_of_receiver_wallets, amount_of_transactions, delay = test_info
        test_info = [1, 1, 5, 50, {'base': 1, 'self': 1.5}]

        self.template_network_mixed_receivers__founder_to_list_of_created_wallets(test_info)

    def test_network_mixed_receivers__throughput_test__high_nodes_low_tx_count(self):
        # num_of_masternodes, num_of_delegates, num_of_receiver_wallets, amount_of_transactions, delay = test_info
        test_info = [2, 2, 5, 20, {'base': 1, 'self': 1.5}]

        self.template_network_mixed_receivers__founder_to_list_of_created_wallets(test_info)

    def test_network_mixed_receivers__throughput_test__high_nodes_high_tx_count(self):
        # num_of_masternodes, num_of_delegates, num_of_receiver_wallets, amount_of_transactions, delay = test_info
        test_info = [2, 2, 5, 50, {'base': 1, 'self': 1.5}]

        self.template_network_mixed_receivers__founder_to_list_of_created_wallets(test_info)

    def test_network_mixed_receivers__throughput_test__2_nodes_1_tx(self):
        # num_of_masternodes, num_of_delegates, num_of_receiver_wallets, amount_of_transactions, delay = test_info
        test_info = [2, 1, 1, 1, {'base': 1, 'self': 1.5}]

        self.template_network_mixed_receivers__founder_to_list_of_created_wallets(test_info)
