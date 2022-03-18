from lamden.nodes.masternode import masternode
from lamden.nodes import base
from lamden import storage
from lamden.crypto.wallet import Wallet
from lamden.crypto.transaction import build_transaction

from contracting.stdlib.bridge.decimal import ContractingDecimal
from contracting.db.driver import InMemDriver, ContractDriver
from contracting.db import encoder

import asyncio
import random
import json
import time
import pprint

from unittest import TestCase

from lamden.nodes.processing_queue import make_tx_message


class TestNode(TestCase):
    def setUp(self):
        self.num_of_nodes = 0

        self.blocks = storage.BlockStorage()

        self.driver = ContractDriver(driver=InMemDriver())

        self.stu_wallet = Wallet()

        self.b = masternode.BlockService(
            blocks=self.blocks,
            driver=self.driver
        )

        self.blocks.flush()
        self.driver.flush()

        self.node = None

        self.tx_history = {}
        self.tx_accumulator ={}
        print("\n")

    def tearDown(self):
        if self.node.running:
            self.stop_node()

        self.b.blocks.flush()
        self.b.driver.flush()

    def start_node(self):
            self.await_async_process(self.node.start)

    def stop_node(self):
            self.await_async_process(self.node.stop)

    def add_currency_balance_to_node(self, node, to, amount):
        node.client.set_var(
            contract='currency',
            variable='balances',
            arguments=[to],
            value=amount
        )
        node.driver.commit()

    def create_a_node(self, constitution=None):
        driver = ContractDriver(driver=InMemDriver())

        dl_wallet = Wallet()
        mn_wallet = Wallet()

        constitution = constitution or {
                'masternodes': [mn_wallet.verifying_key],
                'delegates': [dl_wallet.verifying_key]
            }

        node = base.Node(
            socket_base=f'tcp://127.0.0.1:{self.num_of_nodes}',
            wallet=mn_wallet,
            constitution=constitution,
            driver=driver,
            delay={
                'base': 0,
                'self': 0
            },
            metering=False,
            testing=True
        )

        self.num_of_nodes = self.num_of_nodes + 1

        self.node = node

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

    async def delay_processing_await(self, func, delay):
        await asyncio.sleep(delay)
        if func:
            return await func()

    def await_async_process_work(self, node, msg):
        tasks = asyncio.gather(
            node.work_validator.process_message(msg=msg),
        )
        loop = asyncio.get_event_loop()
        res =  loop.run_until_complete(tasks)

    def send_transactions(self, amount_of_txs, node, sender_wallet):
        for i in range(amount_of_txs):
            receiver_wallet = Wallet()
            amount = str(round(random.uniform(1, 200), 4))
            tx = json.loads(build_transaction(
                wallet=sender_wallet,
                contract="currency",
                function="transfer",
                kwargs={
                    'to': receiver_wallet.verifying_key,
                    'amount': {"__fixed__": amount}
                },
                stamps=100,
                processor=node.wallet.verifying_key,
                nonce=1
            ))

            tx_message = make_tx_message(node.hlc_clock, node.wallet, tx)
            self.await_async_process_work(node=node, msg=tx_message)

            self.tx_history[receiver_wallet.verifying_key] = {
                "amount":amount,
                "tx":tx
            }

    def send_transaction(self, node, sender_wallet, receiver_wallet, index=0):
            #amount = str(round(random.uniform(1, 200), 4))
            amount = str(random.randint(1, 20))
            tx = json.loads(build_transaction(
                wallet=sender_wallet,
                contract="currency",
                function="transfer",
                kwargs={
                    'to': receiver_wallet.verifying_key,
                    'amount': {"__fixed__": amount}
                },
                stamps=100,
                processor=node.wallet.verifying_key,
                nonce=1
            ))

            tx_message = make_tx_message(node.hlc_clock, node.wallet, tx)
            self.await_async_process_work(node=node, msg=tx_message)

            if self.tx_accumulator.get(receiver_wallet.verifying_key, None) is None:
                self.tx_history[index] = {
                    'wallet': receiver_wallet.verifying_key,
                    'amount': ContractingDecimal(amount),
                    'curr': ContractingDecimal(amount),
                    'prev': ContractingDecimal(0)
                }
                self.tx_accumulator[receiver_wallet.verifying_key] = ContractingDecimal(amount)
            else:
                self.tx_history[index] = {
                    'wallet': receiver_wallet.verifying_key,
                    'amount':  ContractingDecimal(amount),
                    'curr': self.tx_accumulator[receiver_wallet.verifying_key] + ContractingDecimal(amount),
                    'prev': self.tx_accumulator[receiver_wallet.verifying_key]
                }
                self.tx_accumulator[receiver_wallet.verifying_key] += ContractingDecimal(amount)

    def await_all_processed(self, node, expected_block_height):
        def check():
            current_height = node.get_current_height()
            if current_height != expected_block_height:
                self.async_sleep(.1)
                check()
        check()

    def test_transaction_throughput__founder_to_new_wallets__queued_and_then_processed(self):
        # Get and start a node
        self.create_a_node()
        # Set the consensus percent to 0 so all processed transactions will "be in consensus"
        self.node.consensus_percent = 0
        self.start_node()

        self.assertTrue(self.node.running)
        self.assertTrue(self.node.validation_queue.running)

        self.node.main_processing_queue.running = False
        self.assertFalse(self.node.main_processing_queue.running)

        # Create a wallet with a balance
        jeff_wallet = Wallet()
        receiver_wallet = Wallet()

        # Seed initial currency balances
        self.add_currency_balance_to_node(node=self.node, to=jeff_wallet.verifying_key, amount=1_000_000_000)

        amount_of_txn = 100
        self.send_transactions(amount_of_txs=amount_of_txn, node=self.node, sender_wallet=jeff_wallet)

        start_time = time.time()
        self.node.main_processing_queue.start()
        self.await_all_processed(node=self.node, expected_block_height=amount_of_txn)
        end_time = time.time()
        print(f'Processing took {end_time - start_time} seconds')


        # ___ VALIDATE TEST RESULTS ___
        # block height equals the amount of transactions processed
        self.assertEqual(amount_of_txn, self.node.get_current_height())

        # All state values reflect the result of the processed transactions
        for key in self.tx_history:
            balance = self.node.executor.driver.get_var(
                contract='currency',
                variable='balances',
                arguments=[key],
                mark=False
            )
            balance = json.loads(encoder.encode(balance))
            if type(balance) is dict:
                balance = balance['__fixed__']

            print(f"{key}: TX = {self.tx_history[key]['amount']} | STATE = {balance}")
            if encoder.encode(balance) == "null":
                pprint.pprint(self.tx_history[key]["tx"])

            self.assertEqual(self.tx_history[key]['amount'], balance)

        self.assertEqual(0, len(self.node.main_processing_queue.read_history))

    def test_transaction_throughput__founder_to_new_wallets__processing_as_added(self):
        # Get and start a node
        self.create_a_node()
        # Set the consensus percent to 0 so all processed transactions will "be in consensus"
        self.node.consensus_percent = 0

        self.start_node()

        self.assertTrue(self.node.running)
        self.assertTrue(self.node.main_processing_queue.running)
        self.assertTrue(self.node.validation_queue.running)

        # Create a wallet with a balance
        jeff_wallet = Wallet()
        receiver_wallet = Wallet()

        # Seed initial currency balances
        self.add_currency_balance_to_node(node=self.node, to=jeff_wallet.verifying_key, amount=1_000_000_000)

        amount_of_txn = 100
        self.send_transactions(amount_of_txs=amount_of_txn, node=self.node, sender_wallet=jeff_wallet)

        start_time = time.time()
        self.await_all_processed(node=self.node, expected_block_height=amount_of_txn)
        end_time = time.time()
        print(f'Processing took {end_time - start_time} seconds')


        # ___ VALIDATE TEST RESULTS ___
        # block height equals the amount of transactions processed
        self.assertEqual(amount_of_txn, self.node.get_current_height())

        # All state values reflect the result of the processed transactions
        for key in self.tx_history:
            balance = self.node.executor.driver.get_var(
                contract='currency',
                variable='balances',
                arguments=[key],
                mark=False
            )
            balance = json.loads(encoder.encode(balance))
            if type(balance) is dict:
                balance = balance['__fixed__']

            print(f"{key}: TX = {self.tx_history[key]['amount']} | STATE = {balance}")
            if encoder.encode(balance) == "null":
                pprint.pprint(self.tx_history[key]["tx"])

            self.assertEqual(self.tx_history[key]['amount'], balance)

        self.assertEqual(0, len(self.node.main_processing_queue.read_history))

    def test_transaction_throughput__founder_to_existing_wallet_list__queued_and_then_processed(self):
        # Get and start a node
        self.create_a_node()

        # Set the consensus percent to 0 so all processed transactions will "be in consensus"
        self.node.consensus_percent = 0
        self.start_node()
        self.assertTrue(self.node.running)
        self.assertTrue(self.node.validation_queue.running)

        self.node.main_processing_queue.running = False
        self.assertFalse(self.node.main_processing_queue.running)


        # Create a wallet with a balance
        jeff_wallet = Wallet()
        num_of_receivers = 5
        receiver_wallets = [Wallet() for i in range(num_of_receivers)]

        # Seed initial currency balances
        self.add_currency_balance_to_node(node=self.node, to=jeff_wallet.verifying_key, amount=1_000_000_000)

        amount_of_txn = 25
        for i in range(amount_of_txn):
            self.send_transaction(
                node=self.node,
                sender_wallet=jeff_wallet,
                receiver_wallet=receiver_wallets[random.randint(0, num_of_receivers-1)],
                index=i+1
            )

        start_time = time.time()
        self.node.main_processing_queue.start()
        self.await_all_processed(node=self.node, expected_block_height=amount_of_txn)
        end_time = time.time()
        print(f'Processing took {end_time - start_time} seconds')

        # ___ VALIDATE TEST RESULTS ___
        # block height equals the amount of transactions processed
        self.assertEqual(amount_of_txn, self.node.get_current_height())

        # All state values reflect the result of the processed transactions
        for key in self.tx_accumulator:
            balance = self.node.executor.driver.get_var(
                contract='currency',
                variable='balances',
                arguments=[key],
                mark=False
            )
            balance = json.loads(encoder.encode(balance))
            if type(balance) is dict:
                balance = balance['__fixed__']

            result = json.loads(encoder.encode(self.tx_accumulator[key]))
            print(f"{key}: TX ACCUMULATOR = {result['__fixed__']} | STATE = {balance}")

            self.assertEqual(result['__fixed__'], balance)

    def test_transaction_throughput__founder_to_existing_wallet_list__processing_as_added(self):
        # Get and start a node
        self.create_a_node()

        # Set the consensus percent to 0 so all processed transactions will "be in consensus"
        self.node.consensus_percent = 0
        self.start_node()

        self.assertTrue(self.node.running)
        self.assertTrue(self.node.main_processing_queue.running)
        self.assertTrue(self.node.validation_queue.running)

        # Create a wallet with a balance
        jeff_wallet = Wallet()
        num_of_receivers = 5
        receiver_wallets = [Wallet() for i in range(num_of_receivers)]

        # Seed initial currency balances
        self.add_currency_balance_to_node(node=self.node, to=jeff_wallet.verifying_key, amount=1_000_000_000)

        amount_of_txn = 100
        for i in range(amount_of_txn):
            self.send_transaction(
                node=self.node,
                sender_wallet=jeff_wallet,
                receiver_wallet=receiver_wallets[random.randint(0, num_of_receivers-1)],
                index=i+1
            )

        start_time = time.time()
        self.await_all_processed(node=self.node, expected_block_height=amount_of_txn)
        end_time = time.time()
        print(f'Processing took {end_time - start_time} seconds')

        # ___ VALIDATE TEST RESULTS ___
        # block height equals the amount of transactions processed
        self.assertEqual(amount_of_txn, self.node.get_current_height())

        # All state values reflect the result of the processed transactions
        for key in self.tx_accumulator:
            balance = self.node.executor.driver.get_var(
                contract='currency',
                variable='balances',
                arguments=[key],
                mark=False
            )
            balance = json.loads(encoder.encode(balance))
            if type(balance) is dict:
                balance = balance['__fixed__']

            result = json.loads(encoder.encode(self.tx_accumulator[key]))
            print(f"{key}: TX ACCUMULATOR = {result['__fixed__']} | STATE = {balance}")

            self.assertEqual(result['__fixed__'], balance)