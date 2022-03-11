from unittest import TestCase
from contracting.db.driver import ContractDriver
from lamden.nodes.processors import block_contender
from lamden.crypto.wallet import Wallet
from lamden.nodes.hlc import HLC_Clock
from copy import deepcopy

from tests.unit.helpers.mock_transactions import get_new_currency_tx, get_tx_message, get_processing_results

import asyncio


class MockValidationQueue():
    def __init__(self, add_to_main_processing_queue):
        self.add_to_main_processing_queue = add_to_main_processing_queue

    def append(self, processing_results):
        self.add_to_main_processing_queue(processing_results=processing_results)

class TestProcessingQueue(TestCase):
    def setUp(self):
        self.wallet = Wallet()
        self.stu_wallet = Wallet()

        self.driver = ContractDriver()
        self.hlc_clock = HLC_Clock()

        self.append_called = False
        self.peer_in_consensus = True
        self.blocks = {}

        self.main_processing_queue = []

        self.validation_queue = MockValidationQueue(
            add_to_main_processing_queue=self.add_to_main_processing_queue
        )

        self.peers = []

        self.last_hlc_in_consensus = self.hlc_clock.get_new_hlc_timestamp()

        self.block_contender = block_contender.Block_Contender(
            testing=True,
            debug=True,
            validation_queue=self.validation_queue,
            get_all_peers=lambda: self.peers,
            get_block_by_hlc=self.get_block_by_hlc,
            check_peer_in_consensus=self.check_peer_in_consensus,
            peer_add_strike=lambda: True,
            wallet=self.wallet,
            get_last_hlc_in_consensus=lambda: self.last_hlc_in_consensus
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

    def add_to_main_processing_queue(self, processing_results):
        self.main_processing_queue.append(processing_results)
        self.append_called = True

    def check_peer_in_consensus(self, signer):
        return self.peer_in_consensus

    def get_block_by_hlc(self, hlc_timestamp):
        return self.blocks.get(hlc_timestamp, None)

    def test_can_append_valid_message_from_external_node(self):
        # Add our wallet to the peer group
        self.peers.append(self.stu_wallet.verifying_key)

        # Create Tx and Results
        tx_message = get_tx_message()
        processing_results = get_processing_results(tx_message=tx_message, node_wallet=self.stu_wallet)

        # Await processing the message
        self.await_process_message(msg=processing_results)

        # Validate test case results
        self.assertTrue(self.append_called)
        self.assertEqual(1, len(self.main_processing_queue))

    def test_can_append_its_own_messages(self):
        tx_message = get_tx_message()
        processing_results = get_processing_results(tx_message=tx_message, node_wallet=self.wallet)

        self.await_process_message(msg=processing_results)

        # Validate test case results
        self.assertTrue(self.append_called)
        self.assertEqual(1, len(self.main_processing_queue))

    def test_does_not_append_if_signer_not_in_peer_group(self):
        tx_message = get_tx_message()
        processing_results = get_processing_results(tx_message=tx_message, node_wallet=self.stu_wallet)

        self.await_process_message(msg=processing_results)

        # Validate test case results
        self.assertFalse(self.append_called)
        self.assertEqual(0, len(self.main_processing_queue))

    def test_does_not_append_invalid_payload(self):
        self.peers.append(self.stu_wallet.verifying_key)

        tx_message = get_tx_message()
        processing_results = get_processing_results(tx_message=tx_message, node_wallet=self.stu_wallet)

        processing_results.pop('proof')

        self.await_process_message(msg=processing_results)

        # Validate test case results
        self.assertFalse(self.append_called)
        self.assertEqual(0, len(self.main_processing_queue))

    def test_does_not_append_invalid_signature(self):
        self.peers.append(self.stu_wallet.verifying_key)

        tx_message = get_tx_message()
        processing_results = get_processing_results(tx_message=tx_message, node_wallet=self.stu_wallet)

        processing_results['proof']['signature'] = 'bad_sig'

        self.await_process_message(msg=processing_results)

        # Validate test case results
        self.assertFalse(self.append_called)
        self.assertEqual(0, len(self.main_processing_queue))

    def test_does_not_append_message_from_out_of_consensus_peer(self):
        # This logic isn't implemented from the node yet but the logic is in the block contender
        self.peers.append(self.stu_wallet.verifying_key)
        self.peer_in_consensus = False

        tx_message = get_tx_message()
        processing_results = get_processing_results(tx_message=tx_message, node_wallet=self.stu_wallet)

        self.await_process_message(msg=processing_results)

        # Validate test case results
        self.assertFalse(self.append_called)
        self.assertEqual(0, len(self.main_processing_queue))

    def test_does_not_append_message_hlc_already_has_consensus(self):
        # This logic isn't implemented from the node yet but the logic is in the block contender
        self.peers.append(self.stu_wallet.verifying_key)

        tx_message = get_tx_message()
        processing_results = get_processing_results(tx_message=tx_message, node_wallet=self.stu_wallet)

        hlc_timestamp = processing_results.get('hlc_timestamp')

        self.last_hlc_in_consensus = self.hlc_clock.get_new_hlc_timestamp()
        self.blocks[hlc_timestamp] = True

        self.await_process_message(msg=processing_results)

        # Validate test case results
        self.assertFalse(self.append_called)
        self.assertEqual(0, len(self.main_processing_queue))

    def test_appends_message_if_hlc_earlier_but_does_not_have_consensus(self):
        # This logic isn't implemented from the node yet but the logic is in the block contender
        self.peers.append(self.stu_wallet.verifying_key)

        tx_message = get_tx_message()
        processing_results = get_processing_results(tx_message=tx_message, node_wallet=self.stu_wallet)

        hlc_timestamp = processing_results.get('hlc_timestamp')

        self.last_hlc_in_consensus = self.hlc_clock.get_new_hlc_timestamp()

        self.await_process_message(msg=processing_results)

        # Validate test case results
        self.assertTrue(self.append_called)
        self.assertEqual(1, len(self.main_processing_queue))