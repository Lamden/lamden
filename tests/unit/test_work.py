from contracting.db.encoder import decode
from lamden.crypto import transaction
from lamden.crypto.canonical import tx_hash_from_tx
from lamden.crypto.wallet import Wallet
from lamden.network import Network
from lamden.nodes.hlc import HLC_Clock
from lamden.nodes.processors.work import WorkValidator, OLDER_HLC_RECEIVED, MASTERNODE_NOT_KNOWN
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

def make_good_message():
    return {
        "tx": {
            "metadata": {
                "signature": "some_sig"
            },
            "payload":{
                "contract": "some_contract",
                "function": "some_function",
                "kwargs": {},
                "nonce": 1,
                "processor": "sending_masternode_vk",
                "stamps_supplied": 1,
                "sender": "some_vk"
            }
        },
        "hlc_timestamp": "0",
        "sender": "sending_masternode_vk",
        "signature": "some_sig"
    }

class TestWorkValidator(TestCase):
    def setUp(self):
        self.hlc_clock = HLC_Clock()
        self.wallet = Wallet()
        self.main_processing_queue = []
        self.network = Network()
        self.last_processed_hlc = self.hlc_clock.get_new_hlc_timestamp()

        self.wv = WorkValidator(
            self.hlc_clock,
            self.wallet,
            self.main_processing_queue,
            self.get_last_processed_hlc,
            self.stop_node,
            self.network
        )
        self.wv.nonces.flush()

    def get_last_processed_hlc(self):
        return self.last_processed_hlc

    def stop_node(self):
        pass

    def make_tx(self, wallet=Wallet()):
        tx = transaction.build_transaction(
            wallet=wallet,
            processor=wallet.verifying_key,
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

        self.assertFalse(self.wv.older_than_last_processed(msg))

    def test_process_message_appends_message_if_valid(self):
        msg = self.make_tx(wallet=self.wallet)
        self.last_processed_hlc = self.hlc_clock.get_new_hlc_timestamp()

        self.process_message(msg)
        
        self.assertEqual(1, len(self.main_processing_queue))

    def test_process_message_appends_message_older_than_last_processed(self):
        msg = self.make_tx(wallet=self.wallet)
        self.last_processed_hlc = self.hlc_clock.get_new_hlc_timestamp()

        with self.assertLogs(level='ERROR') as log:
            self.process_message(msg)
            self.assertIn(f'{msg["hlc_timestamp"]} received AFTER {self.last_processed_hlc} was processed!', log.output[0])
            self.assertEqual(1, len(self.main_processing_queue))

    def test_process_message_doesnt_append_message_if_unknown_masternode(self):
        msg = self.make_tx()

        with self.assertLogs(level='ERROR') as log:
            self.process_message(msg)
            self.assertIn(f'TX Batch received from non-master {msg["sender"][:8]}', log.output[0])
            self.assertIn(f'ERROR:Work Inbox: {MASTERNODE_NOT_KNOWN}', log.output[1])
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

    def test_METHOD_valid_message_payload__TRUE_if_message_is_good_payload(self):
        self.assertTrue(self.wv.valid_message_payload(msg=make_good_message()))

    def test_METHOD_valid_message_payload__FALSE_if_message_is_not_dict_instance(self):
        self.assertFalse(self.wv.valid_message_payload(msg=None))
        self.assertFalse(self.wv.valid_message_payload(msg="message"))

    def test_METHOD_valid_message_payload__FALSE_if_tx_is_not_dict_instance(self):
        message = make_good_message()
        bad_message = message['tx'] = "testing"
        self.assertFalse(self.wv.valid_message_payload(msg=bad_message))
        del message['tx']
        self.assertFalse(self.wv.valid_message_payload(msg=bad_message))

    def test_METHOD_valid_message_payload__FALSE_if_payload_is_not_dict_instance(self):
        message = make_good_message()
        bad_message = message['tx']['payload'] = "testing"
        self.assertFalse(self.wv.valid_message_payload(msg=bad_message))
        del message['tx']['payload']
        self.assertFalse(self.wv.valid_message_payload(msg=bad_message))

    def test_METHOD_valid_message_payload__FALSE_if_payload_contract_is_not_str_instance(self):
        message = make_good_message()
        bad_message = message['tx']['payload']['contract'] = 1
        self.assertFalse(self.wv.valid_message_payload(msg=bad_message))
        del message['tx']['payload']['contract']
        self.assertFalse(self.wv.valid_message_payload(msg=bad_message))

    def test_METHOD_valid_message_payload__FALSE_if_payload_function_is_not_str_instance(self):
        message = make_good_message()
        bad_message = message['tx']['payload']['function'] = 1
        self.assertFalse(self.wv.valid_message_payload(msg=bad_message))
        del message['tx']['payload']['function']
        self.assertFalse(self.wv.valid_message_payload(msg=bad_message))

    def test_METHOD_valid_message_payload__FALSE_if_payload_kwargs_is_not_dict_instance(self):
        message = make_good_message()
        bad_message = message['tx']['payload']['kwargs'] = 1
        self.assertFalse(self.wv.valid_message_payload(msg=bad_message))
        del message['tx']['payload']['kwargs']
        self.assertFalse(self.wv.valid_message_payload(msg=bad_message))

    def test_METHOD_valid_message_payload__FALSE_if_payload_nonce_is_not_int_instance(self):
        message = make_good_message()
        bad_message = message['tx']['payload']['nonce'] = "fail"
        self.assertFalse(self.wv.valid_message_payload(msg=bad_message))
        del message['tx']['payload']['nonce']
        self.assertFalse(self.wv.valid_message_payload(msg=bad_message))

    def test_METHOD_valid_message_payload__FALSE_if_payload_processor_is_not_str_instance(self):
        message = make_good_message()
        bad_message = message['tx']['payload']['processor'] = 1
        self.assertFalse(self.wv.valid_message_payload(msg=bad_message))
        del message['tx']['payload']['processor']
        self.assertFalse(self.wv.valid_message_payload(msg=bad_message))

    def test_METHOD_valid_message_payload__FALSE_if_payload_stamps_supplied_is_not_int_instance(self):
        message = make_good_message()
        bad_message = message['tx']['payload']['stamps_supplied'] = "fail"
        self.assertFalse(self.wv.valid_message_payload(msg=bad_message))
        del message['tx']['payload']['stamps_supplied']
        self.assertFalse(self.wv.valid_message_payload(msg=bad_message))

    def test_METHOD_valid_message_payload__FALSE_if_metadata_is_not_dict_instance(self):
        message = make_good_message()
        bad_message = message['tx']['metadata'] = "fail"
        self.assertFalse(self.wv.valid_message_payload(msg=bad_message))
        del message['tx']['metadata']
        self.assertFalse(self.wv.valid_message_payload(msg=bad_message))

    def test_METHOD_valid_message_payload__FALSE_if_metadata_signature_is_not_str_instance(self):
        message = make_good_message()
        bad_message = message['tx']['metadata']['signature'] = 1
        self.assertFalse(self.wv.valid_message_payload(msg=bad_message))
        del message['tx']['metadata']['signature']
        self.assertFalse(self.wv.valid_message_payload(msg=bad_message))

    def test_METHOD_valid_message_payload__FALSE_if_hlc_timestamp_is_not_str_instance(self):
        message = make_good_message()
        bad_message = message['hlc_timestamp'] = 1
        self.assertFalse(self.wv.valid_message_payload(msg=bad_message))
        del message['hlc_timestamp']
        self.assertFalse(self.wv.valid_message_payload(msg=bad_message))

    def test_METHOD_valid_message_payload__FALSE_if_sender_is_not_str_instance(self):
        message = make_good_message()
        bad_message = message['sender'] = 1
        self.assertFalse(self.wv.valid_message_payload(msg=bad_message))
        del message['sender']
        self.assertFalse(self.wv.valid_message_payload(msg=bad_message))

    def test_METHOD_valid_message_payload__FALSE_if_signature_is_not_str_instance(self):
        message = make_good_message()
        bad_message = message['signature'] = 1
        self.assertFalse(self.wv.valid_message_payload(msg=bad_message))
        del message['signature']
        self.assertFalse(self.wv.valid_message_payload(msg=bad_message))

    def test_METHOD_sent_from_processor__TRUE_if_sender_matches_processor(self):
        self.assertTrue(self.wv.sent_from_processor(message=make_good_message()))

    def test_METHOD_sent_from_processor__FALSE_if_sender_does_not_match_processor(self):
        message = make_good_message()
        message['sender'] = 'bad_sender'
        self.assertFalse(self.wv.sent_from_processor(message=message))

    def test_METHOD_save_nonce__can_set_a_nonce_from_message(self):
        message=make_good_message()
        self.wv.save_nonce(msg=message)

        current_nonce = self.wv.nonces.get_nonce(
            sender=message['tx']['payload']['sender'],
            processor=message['tx']['payload']['processor']
        )
        self.assertTrue(1, current_nonce)

    def test_METHOD_check_nonce__TRUE_if_current_nonce_is_NONE(self):
        self.assertTrue(self.wv.check_nonce(msg=make_good_message()))

    def test_METHOD_check_nonce__TRUE_if_nonce_in_message_is_greater(self):
        message = make_good_message()
        self.wv.nonces.set_nonce(
            sender=message['tx']['payload']['sender'],
            processor=message['tx']['payload']['processor'],
            value=0
        )
        self.assertTrue(self.wv.check_nonce(msg=message))

    def test_METHOD_check_nonce__FALSE_if_nonce_in_message_is_less_than(self):
        message = make_good_message()
        self.wv.nonces.set_nonce(
            sender=message['tx']['payload']['sender'],
            processor=message['tx']['payload']['processor'],
            value=2
        )
        self.assertFalse(self.wv.check_nonce(msg=message))

    def test_METHOD_check_nonce__FALSE_if_nonce_in_message_is_equal(self):
        message = make_good_message()
        self.wv.nonces.set_nonce(
            sender=message['tx']['payload']['sender'],
            processor=message['tx']['payload']['processor'],
            value=1
        )
        self.assertFalse(self.wv.check_nonce(msg=message))
