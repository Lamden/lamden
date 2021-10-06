from tests.integration.mock.mocks_multip import TEST_FOUNDATION_WALLET, Process, MockNetwork, MockMaster, create_fixture_directories, remove_fixture_directories
from lamden.nodes.filequeue import FileQueue

from lamden.crypto.wallet import Wallet
from lamden.crypto import transaction
from contracting.stdlib.bridge.decimal import ContractingDecimal
from contracting.db.driver import InMemDriver, ContractDriver
from contracting.client import ContractingClient
from contracting.db import encoder

import zmq.asyncio
import asyncio
import httpx
from random import randrange
import json
import time
import pprint
import multiprocessing
from unittest import TestCase
from sys import setrecursionlimit
setrecursionlimit(20000)


class TestMultiNode(TestCase):
    def setUp(self):
        self.fixture_directories = ['block_storage', 'file_queue', 'nonces', 'pending-nonces']
        # remove_fixture_directories(self.fixture_directories)
        create_fixture_directories(self.fixture_directories)

        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.network = None

        self.founder_wallet = TEST_FOUNDATION_WALLET
        print("\n")

    def tearDown(self):
        for node_process in self.network.all_nodes():
            try:
                node_process.process.terminate()
            except Exception:
                pass

        self.ctx.destroy()
        self.loop.close()

        remove_fixture_directories(self.fixture_directories)

    def await_async_process(self, process, args={}):
        tasks = asyncio.gather(
            process(**args)
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

    def send_tx(self, parent_connection, sender_wallet=None):
        parent_connection.send(["send_tx", {
            'sender_wallet': sender_wallet or self.founder_wallet
        }])

    def test_network(self):
        self.network = MockNetwork(num_of_masternodes=2, num_of_delegates=2)
        self.await_async_process(self.network.start)
        self.await_async_process(self.network.await_all_started)

        self.assertTrue(self.network.masternodes[0].started)

        self.await_async_process(self.network.stop)

'''
    def test_network_can_propagate_transactions(self):
        # Test that the network can receive a transaction and send it around to all the other nodes

        # Create a network
        network_1 = MockNetwork(
            num_of_delegates=3,
            num_of_masternodes=3,
            ctx=self.ctx,
            metering=False,
            delay={'base': 0.1, 'self': 0.1}
        )
        self.networks.append(network_1)
        self.await_async_process(network_1.start)

        # get a masternode
        masternode_1 = network_1.masternodes[0]

        receiver_wallet = Wallet()
        amount = 100.5

        # create a masternode
        tx = transaction.build_transaction(
            wallet=masternode_1.wallet,
            contract='currency',
            function='transfer',
            kwargs={
                'to': receiver_wallet.verifying_key,
                'amount': {'__fixed__': amount}
            },
            stamps=100,
            processor=masternode_1.wallet.verifying_key,
            nonce=1
        )
        # Give the masternode the transaction
        masternode_1.tx_queue.append(tx.encode())

        # Wait for propagation around network
        self.async_sleep(1)

        # Check that each node ran the transaction
        all_nodes = network_1.all_nodes()
        for node in all_nodes:
            self.assertEqual(masternode_1.obj.last_processed_hlc, node.obj.last_processed_hlc)

    def test_network_can_propagate_results(self):
        # Test that the network can receive a transaction and send it around to all the other nodes

        # Create a network
        network_1 = MockNetwork(
            num_of_delegates=3,
            num_of_masternodes=3,
            ctx=self.ctx,
            metering=False,
            delay={'base': 0.1, 'self': 0.1}
        )
        self.networks.append(network_1)
        self.await_async_process(network_1.start)

        # stop all nodes validation queues so that they collect all results and don't do consensus
        all_nodes = network_1.all_nodes()
        for node in all_nodes:
            node.obj.validation_queue.stop()

        # get a masternode
        masternode_1 = network_1.masternodes[0]

        receiver_wallet = Wallet()
        amount = 100.5

        # create a masternode
        tx = transaction.build_transaction(
            wallet=masternode_1.wallet,
            contract='currency',
            function='transfer',
            kwargs={
                'to': receiver_wallet.verifying_key,
                'amount': {'__fixed__': amount}
            },
            stamps=100,
            processor=masternode_1.wallet.verifying_key,
            nonce=1
        )
        # Give the masternode the transaction
        masternode_1.tx_queue.append(tx.encode())

        # Wait for propagation around network
        self.async_sleep(1)

        hlc_timestamp = masternode_1.obj.last_processed_hlc
        all_solutions = masternode_1.obj.validation_queue.validation_results[hlc_timestamp]['solutions']

        # Check that each node ran the transaction
        for node in all_nodes:
            self.assertIsNotNone(all_solutions[node.wallet.verifying_key])
'''