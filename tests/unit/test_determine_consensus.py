from unittest import TestCase
from lamden.nodes.determine_consensus import DetermineConsensus
from lamden.crypto.wallet import Wallet

from copy import deepcopy

from tests.unit.helpers.mock_transactions import get_new_currency_tx, get_tx_message, get_processing_results
from tests.unit.helpers.mock_processing_results import ValidationResults

import asyncio

class TestDetermineConsensus(TestCase):
    def setUp(self):
        self.wallet = Wallet()
        self.consensus_percent = 51

        self.validation_results = ValidationResults()

        self.determine_consensus = DetermineConsensus(
            consensus_percent=lambda: self.consensus_percent,
            my_wallet=self.wallet
        )

        print("\n")

    def tearDown(self):
        pass

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def new_tx_message(self, masternode):
        receiver_wallet = Wallet()

        tx_info = {
            'wallet': masternode,
            'amount': 100.5,
            'to': receiver_wallet.verifying_key
        }

        transaction = get_new_currency_tx(**tx_info)
        return get_tx_message(tx=transaction, node_wallet=masternode)

    def test_determine_ideal_consensus_matches_me(self):
        my_node_wallet = self.wallet
        other_node_wallet_1 = Wallet()
        other_node_wallet_2 = Wallet()

        processing_results_1, processing_results_2, processing_results_3 = self.validation_results.add_solutions(
            amount_of_solutions=3,
            node_wallets=[my_node_wallet, other_node_wallet_1, other_node_wallet_2],
            masternode=my_node_wallet
        )

        hlc_timestamp = processing_results_1.get('hlc_timestamp')
        solution = processing_results_1['proof'].get('tx_result_hash')

        consensus_results = self.determine_consensus.check_consensus(
            num_of_participants=3,
            solutions=self.validation_results.all_results[hlc_timestamp].get('solutions'),
            last_check_info=self.validation_results.all_results[hlc_timestamp].get('last_check_info')
        )

        self.assertTrue(consensus_results.get('has_consensus'))
        self.assertEqual('ideal', consensus_results.get('consensus_type'))
        self.assertTrue(consensus_results.get('ideal_consensus_possible'))
        self.assertTrue(consensus_results.get('matches_me'))
        self.assertEqual(solution, consensus_results.get('solution'))
        self.assertEqual(solution, consensus_results.get('my_solution'))
        self.assertEqual(2, consensus_results.get('consensus_needed'))

    def test_determine_ideal_consensus_DOES_NOT_match_me(self):
        my_node_wallet = self.wallet
        other_node_wallet_1 = Wallet()
        other_node_wallet_2 = Wallet()

        tx_message = self.new_tx_message(masternode=other_node_wallet_1)

        hlc_timestamp = tx_message['hlc_timestamp']

        # Add a bad tx_result for this node
        tx_message_bad = deepcopy(tx_message)
        tx_message_bad['tx']['payload']['kwargs']['to'] = 'testing_vk'
        my_processing_results = self.validation_results.add_solution(
            tx_message=tx_message_bad,
            node_wallet=my_node_wallet
        )

        # Add two good results from other nodes
        processing_results_1 = self.validation_results.add_solution(
            tx_message=tx_message,
            node_wallet=other_node_wallet_1
        )

        self.validation_results.add_solution(
            tx_message=tx_message,
            node_wallet=other_node_wallet_2
        )

        my_solution = my_processing_results['proof'].get('tx_result_hash')
        solution = processing_results_1['proof'].get('tx_result_hash')

        consensus_results = self.determine_consensus.check_consensus(
            num_of_participants=3,
            solutions=self.validation_results.all_results[hlc_timestamp].get('solutions'),
            last_check_info=self.validation_results.all_results[hlc_timestamp].get('last_check_info')
        )

        self.assertTrue(consensus_results.get('has_consensus'))
        self.assertEqual('ideal', consensus_results.get('consensus_type'))
        self.assertTrue(consensus_results.get('ideal_consensus_possible'))
        self.assertFalse(consensus_results.get('matches_me'))
        self.assertEqual(solution, consensus_results.get('solution'))
        self.assertEqual(my_solution, consensus_results.get('my_solution'))
        self.assertEqual(2, consensus_results.get('consensus_needed'))

    def test_determine_ideal_consensus_MISSING_my_solution(self):
        other_node_wallet_1 = Wallet()
        other_node_wallet_2 = Wallet()

        processing_results_1, processing_results_2 = self.validation_results.add_solutions(
            amount_of_solutions=2,
            node_wallets=[other_node_wallet_1, other_node_wallet_2],
            masternode=other_node_wallet_1
        )

        hlc_timestamp = processing_results_1.get('hlc_timestamp')
        solution = processing_results_1['proof'].get('tx_result_hash')

        consensus_results = self.determine_consensus.check_consensus(
            num_of_participants=3,
            solutions=self.validation_results.all_results[hlc_timestamp].get('solutions'),
            last_check_info=self.validation_results.all_results[hlc_timestamp].get('last_check_info')
        )

        print(consensus_results)

        self.assertTrue(consensus_results.get('has_consensus'))
        self.assertEqual('ideal', consensus_results.get('consensus_type'))
        self.assertTrue(consensus_results.get('ideal_consensus_possible'))
        self.assertFalse(consensus_results.get('matches_me'))
        self.assertEqual(solution, consensus_results.get('solution'))
        self.assertEqual(None, consensus_results.get('my_solution'))
        self.assertEqual(2, consensus_results.get('consensus_needed'))

    def test_determine_next_ideal_consensus_on_updated_information_from_me(self):
        my_node_wallet = self.wallet
        other_node_wallet_1 = Wallet()

        tx_message = self.new_tx_message(masternode=other_node_wallet_1)

        hlc_timestamp = tx_message['hlc_timestamp']

        # Add a bad tx_result for this node
        tx_message_bad = deepcopy(tx_message)
        tx_message_bad['tx']['payload']['kwargs']['to'] = 'testing_vk'
        self.validation_results.add_solution(
            tx_message=tx_message_bad,
            node_wallet=my_node_wallet
        )

        # Add a good results from other nodes
        processing_results_1 = self.validation_results.add_solution(
            tx_message=tx_message,
            node_wallet=other_node_wallet_1
        )

        solution = processing_results_1['proof'].get('tx_result_hash')

        # Process consensus
        consensus_results_1 = self.determine_consensus.check_consensus(
            num_of_participants=3,
            solutions=self.validation_results.all_results[hlc_timestamp].get('solutions'),
            last_check_info=self.validation_results.all_results[hlc_timestamp].get('last_check_info')
        )

        # Verify consensus is FALSE
        self.assertFalse(consensus_results_1['has_consensus'])

        # Add proper solution for this node

        self.validation_results.add_solution(
            tx_message=tx_message,
            node_wallet=my_node_wallet
        )

        # Process consensus
        consensus_results_2 = self.determine_consensus.check_consensus(
            num_of_participants=3,
            solutions=self.validation_results.all_results[hlc_timestamp].get('solutions'),
            last_check_info=self.validation_results.all_results[hlc_timestamp].get('last_check_info')
        )

        # Verify consensus is TRUE
        self.assertTrue(consensus_results_2.get('has_consensus'))
        self.assertEqual('ideal', consensus_results_2.get('consensus_type'))
        self.assertTrue(consensus_results_2.get('ideal_consensus_possible'))
        self.assertTrue(consensus_results_2.get('matches_me'))
        self.assertEqual(solution, consensus_results_2.get('solution'))
        self.assertEqual(solution, consensus_results_2.get('my_solution'))
        self.assertEqual(2, consensus_results_2.get('consensus_needed'))

    def test_determine_ideal_consensus_on_updated_information_from_peer(self):
        my_node_wallet = self.wallet
        other_node_wallet_1 = Wallet()

        tx_message = self.new_tx_message(masternode=other_node_wallet_1)

        hlc_timestamp = tx_message['hlc_timestamp']

        # Add a good results from this THIS node
        processing_results_1 =  self.validation_results.add_solution(
            tx_message=tx_message,
            node_wallet=my_node_wallet
        )

        # Add a bad solution from another node
        self.validation_results.add_bad_solution(
            tx_message=tx_message,
            node_wallet=other_node_wallet_1
        )

        solution = processing_results_1['proof'].get('tx_result_hash')

        # Process consensus
        consensus_results_1 = self.determine_consensus.check_consensus(
            num_of_participants=3,
            solutions=self.validation_results.all_results[hlc_timestamp].get('solutions'),
            last_check_info=self.validation_results.all_results[hlc_timestamp].get('last_check_info')
        )

        # Verify consensus is FALSE
        self.assertFalse(consensus_results_1['has_consensus'])

        # Add proper solution for this node

        self.validation_results.add_solution(
            tx_message=tx_message,
            node_wallet=other_node_wallet_1
        )

        # Process consensus
        consensus_results_2 = self.determine_consensus.check_consensus(
            num_of_participants=3,
            solutions=self.validation_results.all_results[hlc_timestamp].get('solutions'),
            last_check_info=self.validation_results.all_results[hlc_timestamp].get('last_check_info')
        )

        # Verify consensus is TRUE
        self.assertTrue(consensus_results_2.get('has_consensus'))
        self.assertEqual('ideal', consensus_results_2.get('consensus_type'))
        self.assertTrue(consensus_results_2.get('ideal_consensus_possible'))
        self.assertTrue(consensus_results_2.get('matches_me'))
        self.assertEqual(solution, consensus_results_2.get('solution'))
        self.assertEqual(solution, consensus_results_2.get('my_solution'))
        self.assertEqual(2, consensus_results_2.get('consensus_needed'))

    def test_process_next_eager_consensus_matches_me(self):
        '''
            Eager consensus test setup will have 4 nodes. Two are in consensus and the other two differ from consensus
            and each other.
            This is a 51% consensus and the validation queue should decide on eager consensus only when all 4 results
            are in.
        '''

        my_node_wallet = self.wallet
        other_node_wallet_1 = Wallet()
        other_node_wallet_2 = Wallet()
        other_node_wallet_3 = Wallet()

        tx_message = self.new_tx_message(masternode=other_node_wallet_1)

        processing_results_1 = self.validation_results.add_solution(
            tx_message=tx_message,
            node_wallet=my_node_wallet
        )
        self.validation_results.add_solution(
            tx_message=tx_message,
            node_wallet=other_node_wallet_1
        )
        self.validation_results.add_bad_solution(
            tx_message=tx_message,
            node_wallet=other_node_wallet_2
        )
        self.validation_results.add_bad_solution(
            tx_message=tx_message,
            node_wallet=other_node_wallet_3,
            to="testing_2"
        )

        hlc_timestamp = processing_results_1.get('hlc_timestamp')
        solution = processing_results_1['proof'].get('tx_result_hash')

        consensus_results = self.determine_consensus.check_consensus(
            num_of_participants=4,
            solutions=self.validation_results.all_results[hlc_timestamp].get('solutions'),
            last_check_info=self.validation_results.all_results[hlc_timestamp].get('last_check_info')
        )

        self.assertTrue(consensus_results.get('has_consensus'))
        self.assertEqual('eager', consensus_results.get('consensus_type'))
        self.assertFalse(consensus_results.get('ideal_consensus_possible'))
        self.assertTrue(consensus_results.get('eager_consensus_possible'))
        self.assertTrue(consensus_results.get('matches_me'))
        self.assertEqual(solution, consensus_results.get('solution'))
        self.assertEqual(solution, consensus_results.get('my_solution'))
        self.assertEqual(3, consensus_results.get('consensus_needed'))

    def test_process_next_eager_consensus_DOES_NOT_match_me(self):
        '''
            Eager consensus test setup will have 4 nodes. Two are in consensus and the other two differ from consensus
            and each other.
            This is a 50% consensus and the validation queue should decide on eager consensus only when all 4 results
            are in.
            I will be in the group that differs
        '''

        my_node_wallet = self.wallet
        other_node_wallet_1 = Wallet()
        other_node_wallet_2 = Wallet()
        other_node_wallet_3 = Wallet()

        tx_message = self.new_tx_message(masternode=other_node_wallet_1)

        processing_results_1 = self.validation_results.add_solution(
            tx_message=tx_message,
            node_wallet=other_node_wallet_1
        )
        self.validation_results.add_solution(
            tx_message=tx_message,
            node_wallet=other_node_wallet_2
        )
        my_processing_results = self.validation_results.add_bad_solution(
            tx_message=tx_message,
            node_wallet=my_node_wallet
        )
        self.validation_results.add_bad_solution(
            tx_message=tx_message,
            node_wallet=other_node_wallet_3,
            to="testing_2"
        )

        hlc_timestamp = processing_results_1.get('hlc_timestamp')
        solution = processing_results_1['proof'].get('tx_result_hash')
        my_solution = my_processing_results['proof'].get('tx_result_hash')

        consensus_results = self.determine_consensus.check_consensus(
            num_of_participants=4,
            solutions=self.validation_results.all_results[hlc_timestamp].get('solutions'),
            last_check_info=self.validation_results.all_results[hlc_timestamp].get('last_check_info')
        )

        self.assertTrue(consensus_results.get('has_consensus'))
        self.assertEqual('eager', consensus_results.get('consensus_type'))
        self.assertFalse(consensus_results.get('ideal_consensus_possible'))
        self.assertTrue(consensus_results.get('eager_consensus_possible'))
        self.assertFalse(consensus_results.get('matches_me'))
        self.assertEqual(solution, consensus_results.get('solution'))
        self.assertEqual(my_solution, consensus_results.get('my_solution'))
        self.assertEqual(3, consensus_results.get('consensus_needed'))

    def test_process_next_failed_consensus_matches_me(self):
        '''
            Failed consensus setup will have 3 nodes all with different solutions.
            I will have the top solution when determining higher numerical hex value.
            This one is tricky due to the way failed consensus is established which is to get the numerical value of
            the result hash. I will have to manually alter the results hashes to test this.
        '''
        my_node_wallet = self.wallet
        other_node_wallet_1 = Wallet()

        tx_message = self.new_tx_message(masternode=other_node_wallet_1)

        my_processing_results = self.validation_results.add_solution(
            tx_message=tx_message,
            node_wallet=my_node_wallet
        )
        processing_results_1 = self.validation_results.add_bad_solution(
            tx_message=tx_message,
            node_wallet=other_node_wallet_1
        )

        hlc_timestamp = processing_results_1.get('hlc_timestamp')

        solution_1 = processing_results_1['proof'].get('tx_result_hash')
        my_solution = my_processing_results['proof'].get('tx_result_hash')

        solution_1_int = int(solution_1, 16)
        my_solution_int = int(my_solution, 16)

        winning_solution = solution_1

        if my_solution_int < solution_1_int:
            winning_solution = my_solution

        consensus_results = self.determine_consensus.check_consensus(
            num_of_participants=2,
            solutions=self.validation_results.all_results[hlc_timestamp].get('solutions'),
            last_check_info=self.validation_results.all_results[hlc_timestamp].get('last_check_info')
        )

        self.assertTrue(consensus_results.get('has_consensus'))
        self.assertEqual('failed', consensus_results.get('consensus_type'))
        self.assertFalse(consensus_results.get('ideal_consensus_possible'))
        self.assertFalse(consensus_results.get('eager_consensus_possible'))
        self.assertEqual(winning_solution == my_solution, consensus_results.get('matches_me'))
        self.assertEqual(winning_solution, consensus_results.get('solution'))
        self.assertEqual(my_solution, consensus_results.get('my_solution'))
        self.assertEqual(2, consensus_results.get('consensus_needed'))

    def test_process_fall_through_from_ideal_to_failure(self):
        '''
            This test will add results and process after each one. Making sure the validation queue can switch between
            the consensus types as new info comes in.
            Failed consensus setup will have 6 and they will tie for consensus and that will not be known till the 4th
            result comes in.
            I will NOT have the top solution when determining higher numerical hex value

            consensus: 51%
            peers: 6
            Consensus Can Run and Ideal Possible: 2:1:1
            Ideal Not Possible 2:2:1
            Eager Possible: 2:2:1
            Failed 2:2:2
        '''


        my_node_wallet = self.wallet
        other_node_wallet_1 = Wallet()
        other_node_wallet_2 = Wallet()
        other_node_wallet_3 = Wallet()
        other_node_wallet_4 = Wallet()
        other_node_wallet_5 = Wallet()

        tx_message = self.new_tx_message(masternode=other_node_wallet_1)
        hlc_timestamp = tx_message['hlc_timestamp']

        # Add 2 matching solutions. This won't run consensus because we don't have enough a consensus amount of peers
        # to attempt checking

        self.validation_results.add_solution_change_result(
            tx_message=tx_message,
            node_wallet=my_node_wallet,
            hlc_timestamp=hlc_timestamp,
            new_result="1"
        )
        self.validation_results.add_solution_change_result(
            tx_message=tx_message,
            node_wallet=other_node_wallet_1,
            hlc_timestamp=hlc_timestamp,
            new_result="1"
        )

        consensus_results_1 = self.determine_consensus.check_consensus(
            num_of_participants=6,
            solutions=self.validation_results.all_results[hlc_timestamp].get('solutions'),
            last_check_info=self.validation_results.all_results[hlc_timestamp].get('last_check_info')
        )

        self.validation_results.add_consensus_result(
            hlc_timestamp=hlc_timestamp,
            consensus_result=consensus_results_1
        )

        self.assertFalse(consensus_results_1.get('has_consensus'))
        self.assertTrue(consensus_results_1.get('ideal_consensus_possible'))
        self.assertTrue(consensus_results_1.get('eager_consensus_possible'))

        # 2 differing results so that we have more than 51% peers responding, otherwise consensus
        # won't run.  The solution tally will be 2:1:1
        self.validation_results.add_solution_change_result(
            tx_message=tx_message,
            node_wallet=other_node_wallet_2,
            hlc_timestamp=hlc_timestamp,
            new_result="2"
        )
        self.validation_results.add_solution_change_result(
            tx_message=tx_message,
            node_wallet=other_node_wallet_3,
            hlc_timestamp=hlc_timestamp,
            new_result="3"
        )

        consensus_results_2 = self.determine_consensus.check_consensus(
            num_of_participants=6,
            solutions=self.validation_results.all_results[hlc_timestamp].get('solutions'),
            last_check_info=self.validation_results.all_results[hlc_timestamp].get('last_check_info')
        )

        self.validation_results.add_consensus_result(
            hlc_timestamp=hlc_timestamp,
            consensus_result=consensus_results_2
        )

        self.assertFalse(consensus_results_2.get('has_consensus'))
        self.assertTrue(consensus_results_2.get('ideal_consensus_possible'))
        self.assertTrue(consensus_results_2.get('eager_consensus_possible'))

        # Add another result to match an existing making the solution tally 2:2:1.  At this point ideal consensus should
        # report not possible but eager still is
        self.validation_results.add_solution_change_result(
            tx_message=tx_message,
            node_wallet=other_node_wallet_4,
            hlc_timestamp=hlc_timestamp,
            new_result="2"
        )

        consensus_results_3 = self.determine_consensus.check_consensus(
            num_of_participants=6,
            solutions=self.validation_results.all_results[hlc_timestamp].get('solutions'),
            last_check_info=self.validation_results.all_results[hlc_timestamp].get('last_check_info')
        )

        self.validation_results.add_consensus_result(
            hlc_timestamp=hlc_timestamp,
            consensus_result=consensus_results_3
        )

        self.assertFalse(consensus_results_3.get('has_consensus'))
        self.assertFalse(consensus_results_3.get('ideal_consensus_possible'))
        self.assertTrue(consensus_results_3.get('eager_consensus_possible'))

        # Add one more result, which will tie up the tally 2:2:2. With all 6 nodes reporting in a tie this will fall
        # into failed consensus.

        self.validation_results.add_solution_change_result(
            tx_message=tx_message,
            node_wallet=other_node_wallet_5,
            hlc_timestamp=hlc_timestamp,
            new_result="3"
        )

        consensus_results_4 = self.determine_consensus.check_consensus(
            num_of_participants=6,
            solutions=self.validation_results.all_results[hlc_timestamp].get('solutions'),
            last_check_info=self.validation_results.all_results[hlc_timestamp].get('last_check_info')
        )

        self.validation_results.add_consensus_result(
            hlc_timestamp=hlc_timestamp,
            consensus_result=consensus_results_4
        )

        self.assertFalse(consensus_results_4.get('ideal_consensus_possible'))
        self.assertFalse(consensus_results_4.get('eager_consensus_possible'))
        self.assertTrue(consensus_results_4.get('has_consensus'))
        self.assertEqual('failed', consensus_results_4.get('consensus_type'))
        self.assertEqual('1', consensus_results_4.get('solution'))
        self.assertEqual('1', consensus_results_4.get('my_solution'))
        self.assertTrue(consensus_results_4.get('matches_me'))

    def test_tally_solutions(self):
        tx_message = self.new_tx_message(masternode=Wallet())
        hlc_timestamp = tx_message['hlc_timestamp']

        # Add my result
        self.validation_results.add_solution_change_result(
            tx_message=tx_message,
            node_wallet=self.wallet,
            hlc_timestamp=hlc_timestamp,
            new_result="1"
        )

        # Add some nodes with another result
        self.validation_results.add_solution_change_result(
            tx_message=tx_message,
            node_wallet=Wallet(),
            hlc_timestamp=hlc_timestamp,
            new_result="2"
        )
        self.validation_results.add_solution_change_result(
            tx_message=tx_message,
            node_wallet=Wallet(),
            hlc_timestamp=hlc_timestamp,
            new_result="2"
        )

        # Add some nodes with a 3rd result
        self.validation_results.add_solution_change_result(
            tx_message=tx_message,
            node_wallet=Wallet(),
            hlc_timestamp=hlc_timestamp,
            new_result="3"
        )
        self.validation_results.add_solution_change_result(
            tx_message=tx_message,
            node_wallet=Wallet(),
            hlc_timestamp=hlc_timestamp,
            new_result="3"
        )
        self.validation_results.add_solution_change_result(
            tx_message=tx_message,
            node_wallet=Wallet(),
            hlc_timestamp=hlc_timestamp,
            new_result="3"
        )


        tally = self.determine_consensus.tally_solutions(
            solutions=self.validation_results.all_results[hlc_timestamp]['solutions']
        )

        self.assertEqual(1, tally['tallies']['1'])
        self.assertEqual(2, tally['tallies']['2'])
        self.assertEqual(3, tally['tallies']['3'])

        for result in tally['results_list']:
            self.assertEqual(result['consensus_amount'], int(result['solution']))

        self.assertEqual(1, len(tally['top_solutions_list']))
        self.assertEqual('3', tally['top_solutions_list'][0]['solution'])
        self.assertEqual(3, tally['top_solutions_list'][0]['consensus_amount'])

        self.assertFalse(tally['is_tied'])

    def test_tally_solutions_tied(self):
        tx_message = self.new_tx_message(masternode=Wallet())
        hlc_timestamp = tx_message['hlc_timestamp']

        # Add my result
        self.validation_results.add_solution_change_result(
            tx_message=tx_message,
            node_wallet=self.wallet,
            hlc_timestamp=hlc_timestamp,
            new_result="1"
        )

        # Add some nodes with a different result
        self.validation_results.add_solution_change_result(
            tx_message=tx_message,
            node_wallet=Wallet(),
            hlc_timestamp=hlc_timestamp,
            new_result="2"
        )
        self.validation_results.add_solution_change_result(
            tx_message=tx_message,
            node_wallet=Wallet(),
            hlc_timestamp=hlc_timestamp,
            new_result="2"
        )

        # Add some nodes with another different result
        self.validation_results.add_solution_change_result(
            tx_message=tx_message,
            node_wallet=Wallet(),
            hlc_timestamp=hlc_timestamp,
            new_result="3"
        )
        self.validation_results.add_solution_change_result(
            tx_message=tx_message,
            node_wallet=Wallet(),
            hlc_timestamp=hlc_timestamp,
            new_result="3"
        )

        tally = self.determine_consensus.tally_solutions(
            solutions=self.validation_results.all_results[hlc_timestamp]['solutions']
        )

        self.assertEqual(1, tally['tallies']['1'])
        self.assertEqual(2, tally['tallies']['2'])
        self.assertEqual(2, tally['tallies']['3'])

        self.assertEqual(2, len(tally['top_solutions_list']))

        self.assertEqual(2, tally['top_solutions_list'][0]['consensus_amount'])
        self.assertEqual(2, tally['top_solutions_list'][1]['consensus_amount'])

        self.assertTrue(tally['is_tied'])

    def test_check_ideal_consensus_no_consensus_ideal_still_possible(self):
        # test assumption for consensus:
        # number of peers = 10
        # consensus % = 51

        tally_info = {
             'results_list': [
                 {
                     'solution': '1',
                     'consensus_amount': 5
                 },
                 {
                     'solution': '2',
                     'consensus_amount': 4
                 }
             ]
        }
        solutions_missing = 1
        consensus_needed = 6

        ideal_consensus_results = self.determine_consensus.check_ideal_consensus(
            tally_info=tally_info,
            solutions_missing=solutions_missing,
            consensus_needed=consensus_needed,
            my_solution="1"
        )

        self.assertFalse(ideal_consensus_results['has_consensus'])
        self.assertTrue(ideal_consensus_results['ideal_consensus_possible'])

    def test_check_ideal_consensus_no_consensus_ideal_not_possible(self):
        # test assumption for consensus:
        # number of peers = 10
        # consensus % = 51

        tally_info = {
             'results_list': [
                 {
                     'solution': '1',
                     'consensus_amount': 4
                 },
                 {
                     'solution': '2',
                     'consensus_amount': 3
                 },
                 {
                     'solution': '3',
                     'consensus_amount': 3
                 }
             ]
        }
        solutions_missing = 1
        consensus_needed = 6

        ideal_consensus_results = self.determine_consensus.check_ideal_consensus(
            tally_info=tally_info,
            solutions_missing=solutions_missing,
            consensus_needed=consensus_needed,
            my_solution="1"
        )

        self.assertFalse(ideal_consensus_results['has_consensus'])
        self.assertFalse(ideal_consensus_results['ideal_consensus_possible'])

    def test_check_ideal_consensus_has_consensus_matches_me(self):
        # test assumption for consensus:
        # number of peers = 10
        # consensus % = 51

        tally_info = {
             'results_list': [
                 {
                     'solution': '1',
                     'consensus_amount': 6
                 },
                 {
                     'solution': '2',
                     'consensus_amount': 3
                 }
             ]
        }
        solutions_missing = 1
        consensus_needed = 6

        ideal_consensus_results = self.determine_consensus.check_ideal_consensus(
            tally_info=tally_info,
            solutions_missing=solutions_missing,
            consensus_needed=consensus_needed,
            my_solution="1"
        )

        self.assertTrue(ideal_consensus_results['matches_me'])
        self.assertTrue(ideal_consensus_results['has_consensus'])
        self.assertTrue(ideal_consensus_results['ideal_consensus_possible'])
        self.assertEqual('ideal', ideal_consensus_results['consensus_type'])
        self.assertEqual('1', ideal_consensus_results['solution'])
        self.assertEqual('1', ideal_consensus_results['my_solution'])

    def test_check_ideal_consensus_has_consensus_DOES_NOT_match_me(self):
        # test assumption for consensus:
        # number of peers = 10
        # consensus % = 51

        tally_info = {
             'results_list': [
                 {
                     'solution': '1',
                     'consensus_amount': 6
                 },
                 {
                     'solution': '2',
                     'consensus_amount': 3
                 }
             ]
        }
        solutions_missing = 1
        consensus_needed = 6

        ideal_consensus_results = self.determine_consensus.check_ideal_consensus(
            tally_info=tally_info,
            solutions_missing=solutions_missing,
            consensus_needed=consensus_needed,
            my_solution="2"
        )

        self.assertFalse(ideal_consensus_results['matches_me'])
        self.assertTrue(ideal_consensus_results['has_consensus'])
        self.assertTrue(ideal_consensus_results['ideal_consensus_possible'])
        self.assertEqual('ideal', ideal_consensus_results['consensus_type'])
        self.assertEqual('1', ideal_consensus_results['solution'])
        self.assertEqual('2', ideal_consensus_results['my_solution'])

    def test_check_eager_consensus_no_consensus_eager_still_possible(self):
        # test assumption for consensus:
        # number of peers = 20
        # consensus % = 51

        tally_info = {
            'is_tied': True,
            'results_list': [
                {
                     'solution': '1',
                     'consensus_amount': 9
                },
                {
                     'solution': '2',
                     'consensus_amount': 9
                },
                {
                    'solution': '3',
                    'consensus_amount': 1
                }
            ]
        }
        solutions_missing = 1
        consensus_needed = 11

        eager_consensus_results = self.determine_consensus.check_eager_consensus(
            tally_info=tally_info,
            solutions_missing=solutions_missing,
            consensus_needed=consensus_needed,
            my_solution="1"
        )

        self.assertFalse(eager_consensus_results['has_consensus'])
        self.assertTrue(eager_consensus_results['eager_consensus_possible'])

    def test_check_eager_consensus_no_consensus_eager_not_possible(self):
        # test assumption for consensus:
        # number of peers = 20
        # consensus % = 51

        tally_info = {
            'is_tied': True,
            'results_list': [
                {
                    'solution': '1',
                    'consensus_amount': 10
                },
                {
                    'solution': '2',
                    'consensus_amount': 10
                }
            ]
        }
        solutions_missing = 0
        consensus_needed = 11

        eager_consensus_results = self.determine_consensus.check_eager_consensus(
            tally_info=tally_info,
            solutions_missing=solutions_missing,
            consensus_needed=consensus_needed,
            my_solution="1"
        )

        self.assertFalse(eager_consensus_results['has_consensus'])
        self.assertFalse(eager_consensus_results['eager_consensus_possible'])

    def test_check_eager_consensus_has_consensus_matches_me(self):
        # test assumption for consensus:
        # number of peers = 20
        # consensus % = 51

        tally_info = {
            'is_tied': False,
            'results_list': [
                 {
                     'solution': '1',
                     'consensus_amount': 10
                 },
                 {
                     'solution': '2',
                     'consensus_amount': 8
                 },
                 {
                     'solution': '3',
                     'consensus_amount': 1
                 }
            ],
        }
        solutions_missing = 1
        consensus_needed = 11

        eager_consensus_results = self.determine_consensus.check_eager_consensus(
            tally_info=tally_info,
            solutions_missing=solutions_missing,
            consensus_needed=consensus_needed,
            my_solution="1"
        )

        self.assertTrue(eager_consensus_results['matches_me'])
        self.assertTrue(eager_consensus_results['has_consensus'])
        self.assertTrue(eager_consensus_results['eager_consensus_possible'])
        self.assertEqual('eager', eager_consensus_results['consensus_type'])
        self.assertEqual('1', eager_consensus_results['solution'])
        self.assertEqual('1', eager_consensus_results['my_solution'])

    def test_check_eager_consensus_has_consensus_DOES_NOT_match_me(self):
        # test assumption for consensus:
        # number of peers = 20
        # consensus % = 51

        tally_info = {
            'is_tied': False,
            'results_list': [
                 {
                     'solution': '1',
                     'consensus_amount': 10
                 },
                 {
                     'solution': '2',
                     'consensus_amount': 8
                 },
                 {
                     'solution': '3',
                     'consensus_amount': 1
                 }
            ]
        }
        solutions_missing = 1
        consensus_needed = 11

        eager_consensus_results = self.determine_consensus.check_eager_consensus(
            tally_info=tally_info,
            solutions_missing=solutions_missing,
            consensus_needed=consensus_needed,
            my_solution="2"
        )

        self.assertFalse(eager_consensus_results['matches_me'])
        self.assertTrue(eager_consensus_results['has_consensus'])
        self.assertTrue(eager_consensus_results['eager_consensus_possible'])
        self.assertEqual('eager', eager_consensus_results['consensus_type'])
        self.assertEqual('1', eager_consensus_results['solution'])
        self.assertEqual('2', eager_consensus_results['my_solution'])

    def test_check_failed_consensus_matches_me(self):
        # test assumption for consensus:
        # number of peers = 20
        # consensus % = 51

        tally_info = {
            'top_solutions_list': [
                 {
                     'solution': '1',
                     'consensus_amount': 10
                 },
                 {
                     'solution': '2',
                     'consensus_amount': 10
                 }
            ]
        }

        consensus_needed = 11

        failed_consensus_results = self.determine_consensus.check_failed_consensus(
            tally_info=tally_info,
            consensus_needed=consensus_needed,
            my_solution="1"
        )

        self.assertTrue(failed_consensus_results['matches_me'])
        self.assertTrue(failed_consensus_results['has_consensus'])
        self.assertEqual('failed', failed_consensus_results['consensus_type'])
        self.assertEqual('1', failed_consensus_results['solution'])
        self.assertEqual('1', failed_consensus_results['my_solution'])

    def test_check_failed_consensus_DOES_NOT_match_me(self):
        # test assumption for consensus:
        # number of peers = 20
        # consensus % = 51

        tally_info = {
            'top_solutions_list': [
                {
                    'solution': '1',
                    'consensus_amount': 10
                },
                {
                    'solution': '2',
                    'consensus_amount': 10
                }
            ]
        }

        consensus_needed = 11

        failed_consensus_results = self.determine_consensus.check_failed_consensus(
            tally_info=tally_info,
            consensus_needed=consensus_needed,
            my_solution="2"
        )

        self.assertFalse(failed_consensus_results['matches_me'])
        self.assertTrue(failed_consensus_results['has_consensus'])
        self.assertEqual('failed', failed_consensus_results['consensus_type'])
        self.assertEqual('1', failed_consensus_results['solution'])
        self.assertEqual('2', failed_consensus_results['my_solution'])