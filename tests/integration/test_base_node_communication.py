from unittest import TestCase
import lamden.new_sockets
from tests.integration.mock.mocks_new import TEST_FOUNDATION_WALLET, MockNetwork, MockDelegate
from tests.integration.mock.create_directories import create_fixture_directories, remove_fixture_directories
from lamden.nodes.filequeue import FileQueue

from lamden.crypto.wallet import Wallet
from lamden.crypto import transaction
from contracting.stdlib.bridge.decimal import ContractingDecimal
from contracting.db.driver import InMemDriver, ContractDriver
from contracting.client import ContractingClient
from contracting.db import encoder
from lamden.crypto import wallet

import zmq.asyncio
import asyncio
from random import randrange
import json
import time
import pprint

class TestMultiNode(TestCase):
    def setUp(self):
        self.fixture_directories = ['block_storage', 'file_queue', 'nonces', 'pending-nonces']
        # remove_fixture_directories(self.fixture_directories)
        create_fixture_directories(self.fixture_directories)

        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.network = None

        self.network2 = None

        self.founder_wallet = TEST_FOUNDATION_WALLET
        print("\n")

    def tearDown(self):
        # try:
        self.network.stop()

        if self.network2 is not None:
            self.network2.stop()
        # except Exception:
        #     pass

        print('tearDown: network.stop complete')
        self.async_sleep(1)

        print('mid tearDown')

        self.ctx.destroy()
        self.loop.close()

        remove_fixture_directories(self.fixture_directories)

        print('finished tearDown')
        # self.async_sleep(2)

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

    def test_network_can_propagate_transactions(self):
        # Test that the network can receive a transaction and send it around to all the other nodes

        # Create a network
        self.network = MockNetwork(
            num_of_delegates=3,
            num_of_masternodes=3,
            ctx=self.ctx,
            metering=False,
            delay={'base': 0.1, 'self': 0.1}
        )

        self.await_async_process(self.network.start)

        # get a masternode
        masternode_1 = self.network.masternodes[0]

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
        all_nodes = self.network.all_nodes()
        for node in all_nodes:
            self.assertEqual(masternode_1.obj.last_processed_hlc, node.obj.last_processed_hlc)
            



    def test_network_can_propagate_results(self):
        # Test that the network can receive a transaction and send it around to all the other nodes

        # Create a network
        self.network = MockNetwork(
            num_of_delegates=3,
            num_of_masternodes=3,
            ctx=self.ctx,
            metering=False,
            delay={'base': 0.1, 'self': 0.1}
        )

        self.await_async_process(self.network.start)

        # stop all nodes validation queues so that they collect all results and don't do consensus
        all_nodes = self.network.all_nodes()
        for node in all_nodes:
            node.obj.validation_queue.stop()

        # get a masternode
        masternode_1 = self.network.masternodes[0]

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

    def test_network_can_reject_unauthorized_delegate_node(self):
        # Test that the network can reject a node that is not authorized

        # Create a network
        self.network = MockNetwork(
            num_of_delegates=0,
            num_of_masternodes=1,
            ctx=self.ctx,
            metering=False,
            delay={'base': 0.1, 'self': 0.1}
        )

        self.network2 = MockNetwork(
            num_of_delegates=1,
            num_of_masternodes=0,
            ctx=self.ctx,
            metering=False,
            delay={'base': 0.1, 'self': 0.1},
            index=1
        )

        self.await_async_process(self.network.start)

        self.await_async_process(self.network2.start)

        # get a masternode
        masternode_1 = self.network.masternodes[0]

        # get a unauthorized delegate
        unauthorized_delegate = self.network2.delegates[0]

        masternode_1_id = masternode_1.wallet.verifying_key
        unauthorized_delegate_key = lamden.new_sockets.z85_key(unauthorized_delegate.wallet.verifying_key)
        self.await_async_process(unauthorized_delegate.obj.network.connect, {'ip': masternode_1.obj.network.socket_id,
                                                                               'key': masternode_1_id})
        # Wait for the unauthorized_delegate_key to have a chance to connect
        self.async_sleep(1)
        # Test that the master node denied the unauthorized delegate
        self.assertTrue(unauthorized_delegate_key in masternode_1.obj.network.router.cred_provider.denied)

    def test_network_can_reject_unauthorized_master_node(self):
        # Test that the network can reject a node that is not authorized

        # Create a network
        self.network = MockNetwork(
            num_of_delegates=1,
            num_of_masternodes=1,
            ctx=self.ctx,
            metering=False,
            delay={'base': 0.1, 'self': 0.1}
        )

        # get a masternode
        masternode_1 = self.network.masternodes[0]

        # get the delegate
        delegate = self.network.delegates[0]

        # start the mater node
        self.await_async_process(self.network.start_masters)
        # Change the wallet of the router so the delegate's public key will not match
        masternode_1.obj.network.router.wallet = wallet.Wallet()

        self.async_sleep(1)

        # start the delegate node
        self.await_async_process(self.network.start_delegates)

        masternode_1_id = masternode_1.wallet.verifying_key
        unauthorized_delegate_key = lamden.new_sockets.z85_key(delegate.wallet.verifying_key)

        # Wait for the unauthorized_delegate_key to have a chance to connect
        self.async_sleep(1)
        # Test that the delegate did not connect to the master node that did not have matching wallet
        self.assertFalse(delegate.obj.network.peers[masternode_1_id].running)
