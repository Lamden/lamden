from contracting.db.driver import ContractDriver
from contracting.client import ContractingClient
from lamden.contracts import sync
from lamden.crypto.wallet import Wallet
from lamden.network import Network
from lamden.nodes.hlc import HLC_Clock
from lamden.nodes.processors.block_contender import Block_Contender, valid_message_payload
from tests.unit.helpers.mock_transactions import get_tx_message, get_processing_results
from unittest import TestCase
import asyncio
import lamden

SAMPLE_MESSAGES = [
    {
        'valid': False
    },
    {
        'tx_result': {},
        'valid': False
    },
    {
        'tx_result': {
            'transaction': 'value'
         },
        'valid': False
    },
    {
        'tx_result': {
            'transaction': 'value'
         },
        'hlc_timestamp': 'value',
        'valid': False
    },
    {
        'tx_result': {
            'transaction': 'value'
         },
        'hlc_timestamp': 'value',
        'proof': {},
        'valid': False
    },
    {
        'tx_result': {
            'transaction': 'value'
         },
        'hlc_timestamp': 'value',
        'proof': {
            'signature': 'value'
         },
        'valid': False
    },
    {
        'tx_result': {
            'transaction': 'value'
         },
        'hlc_timestamp': 'value',
        'proof': {
            'signature': 'value',
            'signer': 'value'
         },
        'valid': True
    }
]


def make_good_message():
    return {
        "tx_result": {
            "hash": "some_hash",
            'transaction': {},
            'status': 0,
            'state': [],
            'stamps_used': 0,
            'result': 'some_result'
        },
        "hlc_timestamp": "0",
        "proof": {
            "signer": "node_vk",
            "signature": "some_sig"
        },
        "rewards": [],
        "tx_message": {
            "sender": "sending_masternode_vk",
            "signature": "some_sig"
        }
    }

class MockValidationQueue:
    def __init__(self):
        self.validation_results = {}
        self.last_hlc_in_consensus = '0'

    def append(self, processing_results):
        hlc_timestamp = processing_results.get('hlc_timestamp')
        self.validation_results[hlc_timestamp] = processing_results

    def __len__(self):
        return len(self.validation_results)

class TestBlockContenderProcessor(TestCase):
    def setUp(self):
        self.wallet = Wallet()
        self.stu_wallet = Wallet()

        self.driver = ContractDriver()
        self.hlc_clock = HLC_Clock()

        self.peer_in_consensus = True
        self.blocks = {}

        self.main_processing_queue = []

        self.validation_queue = MockValidationQueue()

        self.peers = []
        self.peers.append(self.wallet.verifying_key)
        self.peers.append(self.stu_wallet.verifying_key)

        self.last_hlc_in_consensus = self.hlc_clock.get_new_hlc_timestamp()

        network = Network()

        network.get_all_peers = self.get_all_peers

        self.block_contender = Block_Contender(
            testing=True,
            debug=True,
            validation_queue=self.validation_queue,
            get_block_by_hlc=self.get_block_by_hlc,
            wallet=self.wallet,
            network=network
        )

        print("\n")

    def tearDown(self):
        pass

    def await_process_message(self, msg):
        tasks = asyncio.gather(
            self.block_contender.process_message(msg=msg)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def get_all_peers(self):
        return [vk for vk in self.peers]

    def remove_from_peer_group(self, vk):
        self.peers.remove(vk)

    def check_peer_in_consensus(self, signer):
        return self.peer_in_consensus

    def get_block_by_hlc(self, hlc_timestamp):
        return self.blocks.get(hlc_timestamp, None)

    def etest_can_append_valid_message_from_external_node(self):
        # Add our wallet to the peer group
        self.peers.append(self.stu_wallet.verifying_key)

        # Create Tx and Results
        self.driver.driver.set(f'currency.balances:{self.wallet.verifying_key}', 1000)
        tx_message = get_tx_message(wallet=self.wallet)
        processing_results = get_processing_results(tx_message=tx_message, node_wallet=self.stu_wallet)


        # Await processing the message
        self.await_processe_message(msg=processing_results)

        # Validate test case results
        self.assertEqual(1, len(self.validation_queue))

    def test_can_append_its_own_message(self):
        tx_message = get_tx_message()
        processing_results = get_processing_results(tx_message=tx_message, node_wallet=self.wallet)

        self.await_process_message(msg=processing_results)

        # Validate test case results
        self.assertEqual(1, len(self.validation_queue))

    def test_does_not_append_if_signer_not_in_peer_group(self):
        tx_message = get_tx_message()
        processing_results = get_processing_results(tx_message=tx_message, node_wallet=self.stu_wallet)
        self.remove_from_peer_group(vk=self.stu_wallet.verifying_key)

        with self.assertLogs(level='ERROR') as log:
            self.await_process_message(msg=processing_results)
            self.assertIn('Contender sender is not a valid peer!', log.output[0])

            # Validate test case results
            self.assertEqual(0, len(self.validation_queue))

    def test_does_not_append_invalid_payload(self):
        self.peers.append(self.stu_wallet.verifying_key)

        tx_message = get_tx_message()
        processing_results = get_processing_results(tx_message=tx_message, node_wallet=self.stu_wallet)

        processing_results.pop('proof')

        with self.assertLogs(level='ERROR') as log:
            self.await_process_message(msg=processing_results)
            self.assertIn('Received Invalid Processing Results from No Proof provided', log.output[0])
            self.assertIn(f'{processing_results}', log.output[1])

            # Validate test case results
            self.assertEqual(0, len(self.validation_queue))

    def test_does_not_append_invalid_signature(self):
        self.peers.append(self.stu_wallet.verifying_key)

        tx_message = get_tx_message()
        processing_results = get_processing_results(tx_message=tx_message, node_wallet=self.stu_wallet)

        processing_results['proof']['signature'] = 'bad_sig'

        with self.assertLogs(level='DEBUG') as log:
            self.await_process_message(msg=processing_results)
            self.assertIn(f"Could not verify message signature {processing_results['proof']}", log.output[0])

            # Validate test case results
            self.assertEqual(0, len(self.validation_queue))

    def test_does_not_append_message_hlc_already_has_consensus(self):
        # This logic isn't implemented from the node yet but the logic is in the block contender
        self.peers.append(self.stu_wallet.verifying_key)

        tx_message = get_tx_message()
        processing_results = get_processing_results(tx_message=tx_message, node_wallet=self.stu_wallet)

        hlc_timestamp = processing_results.get('hlc_timestamp')

        self.validation_queue.last_hlc_in_consensus = self.hlc_clock.get_new_hlc_timestamp()
        self.blocks[hlc_timestamp] = True

        self.await_process_message(msg=processing_results)

        # Validate test case results
        self.assertEqual(0, len(self.validation_queue))

    def test_appends_message_if_hlc_earlier_but_does_not_have_consensus(self):
        # This logic isn't implemented from the node yet but the logic is in the block contender
        self.peers.append(self.stu_wallet.verifying_key)
        self.block_contender.network.authorize_peer(peer_vk=self.stu_wallet.verifying_key)
        self.driver.driver.set('masternodes.S:members', [self.stu_wallet.verifying_key])
        tx_message = get_tx_message()
        processing_results = get_processing_results(tx_message=tx_message, node_wallet=self.stu_wallet)

        self.validation_queue.last_hlc_in_consensus = self.hlc_clock.get_new_hlc_timestamp()

        self.await_process_message(msg=processing_results)

        # Validate test case results
        self.assertEqual(1, len(self.validation_queue))

    def test__valid_message_payload__TRUE_if_message_is_all_valid(self):
        good_message = make_good_message()
        self.assertTrue(valid_message_payload(msg=good_message))

    def test__valid_message_payload__FALSE_if_message_is_not_dict_or_None(self):
        self.assertFalse(valid_message_payload(msg="some_message"))
        self.assertFalse(valid_message_payload(msg=None))

    def test__valid_message_payload__FALSE_if_tx_result_is_not_dict(self):
        good_message = make_good_message()
        bad_message = good_message['tx_result'] = "some_result"
        self.assertFalse(valid_message_payload(msg=bad_message))
        del good_message['tx_result']
        self.assertFalse(valid_message_payload(msg=bad_message))

    def test__valid_message_payload__FALSE_if_tx_result_hash_is_not_str_or_None(self):
        good_message = make_good_message()
        bad_message = good_message['tx_result']['hash'] = 1
        self.assertFalse(valid_message_payload(msg=bad_message))
        del good_message['tx_result']['hash']
        self.assertFalse(valid_message_payload(msg=bad_message))

    def test__valid_message_payload__FALSE_if_tx_result_transaction_is_not_dict_or_None(self):
        good_message = make_good_message()
        bad_message = good_message['tx_result']['transaction'] = 'some_transaction'
        self.assertFalse(valid_message_payload(msg=bad_message))
        del good_message['tx_result']['transaction']
        self.assertFalse(valid_message_payload(msg=bad_message))

    def test__valid_message_payload__FALSE_if_tx_result_status_is_not_int_or_None(self):
        good_message = make_good_message()
        bad_message = good_message['tx_result']['status'] = 'some_status'
        self.assertFalse(valid_message_payload(msg=bad_message))
        del good_message['tx_result']['status']
        self.assertFalse(valid_message_payload(msg=bad_message))

    def test__valid_message_payload__FALSE_if_tx_result_stamps_used_is_not_int_or_None(self):
        good_message = make_good_message()
        bad_message = good_message['tx_result']['stamps_used'] = 'some_stamps_used'
        self.assertFalse(valid_message_payload(msg=bad_message))
        del good_message['tx_result']['stamps_used']
        self.assertFalse(valid_message_payload(msg=bad_message))

    def test__valid_message_payload__FALSE_if_tx_result_result_is_not_str_or_None(self):
        good_message = make_good_message()
        bad_message = good_message['tx_result']['result'] = 1
        self.assertFalse(valid_message_payload(msg=bad_message))
        del good_message['tx_result']['result']
        self.assertFalse(valid_message_payload(msg=bad_message))

    def test__valid_message_payload__FALSE_if_hlc_timestamp_is_not_str_or_None(self):
        good_message = make_good_message()
        bad_message = good_message['hlc_timestamp'] = 1
        self.assertFalse(valid_message_payload(msg=bad_message))
        del good_message['hlc_timestamp']
        self.assertFalse(valid_message_payload(msg=bad_message))

    def test__valid_message_payload__FALSE_if_rewards_is_not_list_or_None(self):
        good_message = make_good_message()
        bad_message = good_message['rewards'] = "some_rewards_list"
        self.assertFalse(valid_message_payload(msg=bad_message))
        del good_message['rewards']
        self.assertFalse(valid_message_payload(msg=bad_message))

    def test__valid_message_payload__FALSE_if_proof_is_not_dict_or_None(self):
        good_message = make_good_message()
        bad_message = good_message['proof'] = "some_proof"
        self.assertFalse(valid_message_payload(msg=bad_message))
        del good_message['proof']
        self.assertFalse(valid_message_payload(msg=bad_message))

    def test__valid_message_payload__FALSE_if_proof_signature_is_not_str_or_None(self):
        good_message = make_good_message()
        bad_message = good_message['proof']['signature'] = 1
        self.assertFalse(valid_message_payload(msg=bad_message))
        del good_message['proof']['signature']
        self.assertFalse(valid_message_payload(msg=bad_message))

    def test__valid_message_payload__FALSE_if_proof_signer_is_not_str_or_None(self):
        good_message = make_good_message()
        bad_message = good_message['proof']['signer'] = 1
        self.assertFalse(valid_message_payload(msg=bad_message))
        del good_message['proof']['signer']
        self.assertFalse(valid_message_payload(msg=bad_message))

    def test__valid_message_payload__FALSE_if_tx_message_is_not_dict(self):
        good_message = make_good_message()
        bad_message = good_message['tx_message'] = "some_tx_message"
        self.assertFalse(valid_message_payload(msg=bad_message))
        del good_message['tx_message']
        self.assertFalse(valid_message_payload(msg=bad_message))

    def test__valid_message_payload__FALSE_if_tx_message_signature_is_not_str_or_None(self):
        good_message = make_good_message()
        bad_message = good_message['tx_message']['signature'] = 1
        self.assertFalse(valid_message_payload(msg=bad_message))
        del good_message['tx_message']['signature']
        self.assertFalse(valid_message_payload(msg=bad_message))

    def test__valid_message_payload__FALSE_if_tx_message_sender_is_not_str_or_None(self):
        good_message = make_good_message()
        bad_message = good_message['tx_message']['sender'] = 1
        self.assertFalse(valid_message_payload(msg=bad_message))
        del good_message['tx_message']['sender']
        self.assertFalse(valid_message_payload(msg=bad_message))