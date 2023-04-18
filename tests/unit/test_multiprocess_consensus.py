import time
from unittest import TestCase

import hashlib
import asyncio

from lamden.nodes.multiprocess_consensus import MultiProcessConsensus
from lamden.crypto.wallet import Wallet

from tests.unit.helpers.mock_transactions import get_tx_message, get_processing_results
from tests.unit.helpers.mock_processing_results import ValidationResults

class TestMultiProcessConsensus(TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.wallet = Wallet()
        self.consensus_percent = 51

        self.validation_results = {}
        self.peers = ['1', '2']

        self.multiprocess_consensus = MultiProcessConsensus(
            consensus_percent=lambda: self.consensus_percent,
            my_wallet=self.wallet,
            get_peers_for_consensus=lambda: self.peers
        )
        print("\n")


    def tearDown(self):
        self.validation_results = {}

        try:
            self.loop.run_until_complete(self.multiprocess_consensus.wait_for_done())
            self.loop.run_until_complete(asyncio.sleep(10))
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.close()
        except RuntimeError as e:
            print(e)
        except Exception as e:
            print(e)

        print("done teardown")


    def await_multiprocess_consensus(self, validation_results):
        tasks = asyncio.gather(
            self.multiprocess_consensus.start(
                validation_results=validation_results
            )
        )
        res = self.loop.run_until_complete(tasks)

        return res[0]

    def await_multiprocess_done(self):
        tasks = asyncio.gather(
            self.multiprocess_consensus.wait_for_done()
        )
        self.loop.run_until_complete(tasks)

    def test_start_includes_me(self):
        self.validation_results = ValidationResults(my_wallet=self.wallet)

        test_hlc_timestamp = self.validation_results.add_test(num_of_nodes=99, includes_me=True)

        solution = self.validation_results.get_result_hash(
            hlc_timestamp=test_hlc_timestamp,
            node_vk=self.wallet.verifying_key
        )

        # run multiprocessing
        self.peers = []
        for i in range(100):
            self.peers.append(i)

        all_consensus_results = self.await_multiprocess_consensus(
            validation_results=self.validation_results.get_results()
        )

        self.await_multiprocess_done()

        self.assertIsNotNone(all_consensus_results)

        results_1 = all_consensus_results.get(test_hlc_timestamp)

        self.assertTrue(results_1.get('has_consensus'))
        self.assertTrue(results_1.get('ideal_consensus_possible'))
        self.assertEqual('ideal', results_1.get('consensus_type'))
        self.assertEqual(51, results_1.get('consensus_needed'))
        self.assertEqual(solution, results_1.get('solution'))
        self.assertEqual(solution, results_1.get('my_solution'))
        self.assertTrue(results_1.get('matches_me'))

    def test_start_not_includes_me(self):
        self.validation_results = ValidationResults(my_wallet=self.wallet)

        test_hlc_timestamp = self.validation_results.add_test(num_of_nodes=100)

        solution = self.validation_results.get_solution_list(hlc_timestamp=test_hlc_timestamp)[0]

        # run multiprocessing
        self.peers = []
        for i in range(100):
            self.peers.append(i)

        all_consensus_results = self.await_multiprocess_consensus(
            validation_results=self.validation_results.get_results()
        )
        self.await_multiprocess_done()

        self.assertIsNotNone(all_consensus_results)

        results_1 = all_consensus_results.get(test_hlc_timestamp)

        self.assertTrue(results_1.get('has_consensus'))
        self.assertTrue(results_1.get('ideal_consensus_possible'))
        self.assertEqual('ideal', results_1.get('consensus_type'))
        self.assertEqual(51, results_1.get('consensus_needed'))
        self.assertEqual(solution, results_1.get('solution'))
        self.assertEqual(None, results_1.get('my_solution'))
        self.assertFalse(results_1.get('matches_me'))

    def test_start_multiple_hlcs_at_once(self):
        start_time = time.time()
        self.validation_results = ValidationResults(my_wallet=self.wallet)

        hlc_timestamp_test_1 = self.validation_results.add_test(num_of_nodes=99, includes_me=True)
        hlc_timestamp_test_2 = self.validation_results.add_test(num_of_nodes=100)
        hlc_timestamp_test_3 = self.validation_results.add_test(num_of_nodes=49, includes_me=True)

        solution_1 = self.validation_results.get_result_hash(
            hlc_timestamp=hlc_timestamp_test_1,
            node_vk=self.wallet.verifying_key
        )
        solution_2 = self.validation_results.get_solution_list(hlc_timestamp=hlc_timestamp_test_2)[0]

        # run multiprocessing
        self.peers = []
        for i in range(100):
            self.peers.append(i)

        done_loading_test = time.time()

        all_consensus_results = self.await_multiprocess_consensus(
            validation_results=self.validation_results.get_results()
        )
        self.await_multiprocess_done()

        done_running_consensus = time.time()

        self.assertIsNotNone(all_consensus_results)

        # Test results 1
        results_1 = all_consensus_results.get(hlc_timestamp_test_1)

        self.assertTrue(results_1.get('has_consensus'))
        self.assertTrue(results_1.get('ideal_consensus_possible'))
        self.assertEqual('ideal', results_1.get('consensus_type'))
        self.assertEqual(51, results_1.get('consensus_needed'))
        self.assertEqual(solution_1, results_1.get('solution'))
        self.assertEqual(solution_1, results_1.get('my_solution'))
        self.assertTrue(results_1.get('matches_me'))

        # Test results 2
        results_2 = all_consensus_results.get(hlc_timestamp_test_2)
        self.assertTrue(results_2.get('has_consensus'))
        self.assertTrue(results_2.get('ideal_consensus_possible'))
        self.assertEqual('ideal', results_2.get('consensus_type'))
        self.assertEqual(51, results_2.get('consensus_needed'))
        self.assertEqual(solution_2, results_2.get('solution'))
        self.assertEqual(None, results_2.get('my_solution'))
        self.assertFalse(results_2.get('matches_me'))

        # Test results 3
        results_3 = all_consensus_results.get(hlc_timestamp_test_3)
        self.assertFalse(results_3.get('has_consensus'))

        print(f'Setup Time: {done_loading_test - start_time}')
        print(f'Consensus Time: {(done_running_consensus - start_time ) - (done_loading_test - start_time)}')