from unittest import TestCase
from tests.integration.mock.create_directories import create_fixture_directories, remove_fixture_directories

import time
import asyncio
import os
import json

from lamden.nodes.filequeue import FileQueue
from lamden.crypto import transaction
from lamden.crypto.wallet import Wallet


class TestProcessingQueue(TestCase):
    def setUp(self):
        self.root_path = './.lamden/file_queue_test'
        self.tx_queue_path = f"{self.root_path}/txq"
        self.fixture_directories = ['txq']
        #create_fixture_directories(dir_list=self.fixture_directories)

        self.tx_queue = FileQueue(root=self.tx_queue_path)

    def tearDown(self):
        pass
        remove_fixture_directories(root=self.root_path, dir_list=self.fixture_directories)

    def test_append_tx(self):
        receiver_wallet = Wallet()
        node_wallet = Wallet()

        tx = transaction.build_transaction(
            wallet= Wallet(),
            contract='currency',
            function='transfer',
            kwargs={
                'to': receiver_wallet.verifying_key,
                'amount': {'__fixed__': '100.5'}
            },
            stamps=100,
            processor=node_wallet.verifying_key,
            nonce=1
        )

        # Verify the directory is currently empty
        self.assertTrue(len(os.listdir(self.tx_queue_path)) == 0)

        self.tx_queue.append(tx=tx.encode())

        # Verify a file has been created
        self.assertTrue(len(os.listdir(self.tx_queue_path)) == 1)

    def test_pop_tx(self):
        receiver_wallet = Wallet()
        node_wallet = Wallet()

        tx_str = transaction.build_transaction(
            wallet= Wallet(),
            contract='currency',
            function='transfer',
            kwargs={
                'to': receiver_wallet.verifying_key,
                'amount': {'__fixed__': '100.5'}
            },
            stamps=100,
            processor=node_wallet.verifying_key,
            nonce=1
        )

        tx_obj = json.loads(tx_str)
        file_signature = tx_obj['metadata'].get('signature')

        # Verify the directory is currently empty
        self.assertTrue(len(os.listdir(self.tx_queue_path)) == 0)

        self.tx_queue.append(tx=tx_str.encode())

        # Verify a file has been created
        self.assertTrue(len(os.listdir(self.tx_queue_path)) == 1)

        file_tx = self.tx_queue.pop(0)

        self.assertIsNotNone(file_tx)
        self.assertEqual(file_tx['metadata'].get('signature'), file_signature)





