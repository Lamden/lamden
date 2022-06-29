from lamden.crypto import transaction
from lamden.crypto.wallet import Wallet
from lamden.nodes.filequeue import FileQueue
from unittest import TestCase
import json
import os
import pathlib
import shutil

class TestProcessingQueue(TestCase):
    def setUp(self):
        self.tx_queue_path = pathlib.Path('./filequeue_test/')
        self.tx_queue = FileQueue(root=self.tx_queue_path)

    def tearDown(self):
        self.tx_queue.flush()
        shutil.rmtree(self.tx_queue_path)

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
        self.assertTrue(len(os.listdir(self.tx_queue.txq)) == 0)

        self.tx_queue.append(tx=tx.encode())

        # Verify a file has been created
        self.assertEqual(len(self.tx_queue), 1)
        self.assertTrue(len(os.listdir(self.tx_queue.txq)) == 1)

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
        self.assertTrue(len(os.listdir(self.tx_queue.txq)) == 0)

        self.tx_queue.append(tx=tx_str.encode())

        # Verify a file has been created
        self.assertEqual(len(self.tx_queue), 1)
        self.assertTrue(len(os.listdir(self.tx_queue.txq)) == 1)

        file_tx = self.tx_queue.pop(0)

        self.assertIsNotNone(file_tx)
        self.assertEqual(len(self.tx_queue), 0)
        self.assertEqual(file_tx['metadata'].get('signature'), file_signature)