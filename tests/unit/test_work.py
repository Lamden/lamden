from contracting.db.encoder import decode
from lamden.crypto import transaction
from lamden.crypto.canonical import tx_hash_from_tx
from lamden.crypto.wallet import Wallet
from lamden.new_network import Network
from lamden.nodes.hlc import HLC_Clock
from lamden.nodes.processors.work import WorkValidator
from unittest import TestCase
import asyncio

SAMPLE_MESSAGES = [
    {
        'valid': False
    },
    {
        'tx': 'value',
        'valid': False
    },
    {
        'tx': 'value',
        'hlc_timestamp': 'value',
        'valid': False
    },
    {
        'tx': 'value',
        'hlc_timestamp': 'value',
        'sender': 'value',
        'valid': False
    },
    {
        'tx': None,
        'hlc_timestamp': 'value',
        'sender': 'value',
        'signature': 'value',
        'valid' : False
    },    {
        'tx': 'value',
        'hlc_timestamp': None,
        'sender': 'value',
        'signature': 'value',
        'valid' : False
    },
    {
        'tx': 'value',
        'hlc_timestamp': 'value',
        'sender': None,
        'signature': 'value',
        'valid' : False
    },
    {
        'tx': 'value',
        'hlc_timestamp': 'value',
        'sender': 'value',
        'signature': None,
        'valid' : False
    },
    {
        'tx': 'value',
        'hlc_timestamp': 'value',
        'sender': 'value',
        'signature': 'value',
        'valid' : True
    }
]

class TestWorkValidator(TestCase):
    def setUp(self):
        self.hlc_clock = HLC_Clock()
        self.wallet = Wallet()
        self.main_processing_queue = []
        self.network = Network()
        self.last_processed_hlc = HLC_Clock().get_new_hlc_timestamp()

        self.wv = WorkValidator(self.hlc_clock, self.wallet, self.main_processing_queue,
            self.get_last_processed_hlc, self.stop_node, self.network)

    def get_last_processed_hlc(self):
        return self.last_processed_hlc

    def stop_node(self):
        pass

    def make_tx(self, wallet=Wallet()):
        tx = transaction.build_transaction(
            wallet=wallet,
            processor='b' * 64,
            nonce=0,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 123,
                'to': 'nikita'
            },
            stamps=0
        )

        decoded_tx = decode(tx)
        hlc_timestamp = self.hlc_clock.get_new_hlc_timestamp()
        tx_hash = tx_hash_from_tx(tx=decoded_tx)
        msg = f'{tx_hash}{hlc_timestamp}'
        signature = wallet.sign(msg)

        return {
            'tx': decoded_tx,
            'hlc_timestamp': hlc_timestamp,
            'signature': signature,
            'sender': wallet.verifying_key,
        }

    def process_message(self, msg):
        tasks = asyncio.gather(
            self.wv.process_message(msg)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def test_valid_message_payload(self):
        for msg in SAMPLE_MESSAGES:
            if msg['valid']:
                self.assertTrue(self.wv.valid_message_payload(msg))
            else:
                self.assertFalse(self.wv.valid_message_payload(msg))

    def test_known_masternode_returns_true_if_known(self):
        msg = self.make_tx(wallet=self.wallet)

        self.assertTrue(self.wv.known_masternode(msg))

    def test_known_masternode_returns_false_if_unknown(self):
        msg = self.make_tx()
        
        with self.assertLogs(level='ERROR') as log:
            self.assertFalse(self.wv.known_masternode(msg))
            self.assertIn(f'TX Batch received from non-master {msg["sender"][:8]}', log.output[0])

    def test_valid_signature_returns_true_if_valid(self):
        msg = self.make_tx(wallet=self.wallet)

        self.assertTrue(self.wv.valid_signature(msg))

    def test_valid_signature_returns_false_if_invalid(self):
        msg = self.make_tx()
        msg['sender'] = Wallet().verifying_key

        self.assertFalse(self.wv.valid_signature(msg))

    def test_older_than_last_processed_returns_true_if_older(self):
        msg = self.make_tx()
        self.last_processed_hlc = HLC_Clock().get_new_hlc_timestamp()

        self.assertTrue(self.wv.older_than_last_processed(msg))

    def test_older_than_last_processed_returns_false_if_younger(self):
        self.last_processed_hlc = HLC_Clock().get_new_hlc_timestamp()
        msg = self.make_tx()

        with self.assertLogs(level='ERROR') as log:
            self.assertFalse(self.wv.older_than_last_processed(msg))
            self.assertIn(f'{msg["hlc_timestamp"]} received AFTER {self.last_processed_hlc} was processed!', log.output[0])

    def test_process_message_appends_message_if_valid(self):
        msg = self.make_tx(wallet=self.wallet)
        self.last_processed_hlc = HLC_Clock().get_new_hlc_timestamp()

        self.process_message(msg)
        
        self.assertEqual(1, len(self.main_processing_queue))

    def test_process_message_appends_message_older_than_last_processed(self):
        msg = self.make_tx(wallet=self.wallet)

        with self.assertLogs(level='ERROR') as log:
            self.process_message(msg)
            self.assertIn(f'{msg["hlc_timestamp"]} received AFTER {self.last_processed_hlc} was processed!', log.output[0])
            self.assertEqual(1, len(self.main_processing_queue))

    def test_process_message_doesnt_append_message_if_unknown_masternode(self):
        msg = self.make_tx()

        with self.assertLogs(level='ERROR') as log:
            self.process_message(msg)
            self.assertIn(f'TX Batch received from non-master {msg["sender"][:8]}', log.output[0])
            self.assertIn('Not Known Master', log.output[1])
            self.assertEqual(0, len(self.main_processing_queue))

    def test_process_message_doesnt_append_message_if_not_valid(self):
        for invalid_msg in SAMPLE_MESSAGES:
            if not invalid_msg['valid']:
                with self.assertLogs(level='DEBUG') as log:
                    self.process_message(invalid_msg)
                    self.assertIn('BAD MESSAGE PAYLOAD', log.output[0])
                    self.assertIn(f'{invalid_msg}', log.output[1])
                    self.assertEqual(0, len(self.main_processing_queue))

    def test_process_message_doesnt_append_message_with_invalid_signature(self):
        msg = self.make_tx()
        msg['sender'] = self.wallet.verifying_key

        with self.assertLogs(level='ERROR') as log:
            self.process_message(msg)
            self.assertIn(f'Invalid signature received in transaction from master {msg["sender"][:8]}', log.output[0])
            self.assertEqual(0, len(self.main_processing_queue))
