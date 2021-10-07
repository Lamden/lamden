from unittest import TestCase
from contracting.db.driver import ContractDriver
from lamden.nodes import validation_queue
from lamden.crypto.wallet import Wallet
from lamden.nodes.hlc import HLC_Clock
from copy import deepcopy

from tests.unit.helpers.mock_transactions import get_new_currency_tx, get_tx_message, get_processing_results

import asyncio

class TestProcessingQueue(TestCase):
    def setUp(self):
        self.wallet = Wallet()
        self.driver = ContractDriver()
        self.hlc_clock = HLC_Clock()

        self.running = True

        self.consensus_percent = 51
        self.num_of_peers = 0

        self.hard_apply_block_called = False
        self.set_peers_not_in_consensus_called = False

        self.current_block = 64 * f'0'

        self.validation_queue = validation_queue.ValidationQueue(
            driver=self.driver,
            wallet=self.wallet,
            consensus_percent=lambda: self.consensus_percent,
            get_peers_for_consensus=self.get_peers_for_consensus,
            hard_apply_block=self.hard_apply_block,
            set_peers_not_in_consensus=self.set_peers_not_in_consensus,
            stop_node=self.stop,
            testing=True,
            start_all_queues=self.start_all_queues,
            stop_all_queues=self.stop_all_queues,
            get_block_by_hlc=self.get_block_by_hlc
        )

        print("\n")

    def tearDown(self):
        self.validation_queue.stop()
        self.validation_queue.flush()

    def stop(self):
        self.running = False

    def get_block_by_hlc(self, hlc_timestamp):
        return None

    async def stop_all_queues(self):
        return

    def start_all_queues(self):
        return

    def get_peers_for_consensus(self):
        peers = {}
        for i in range(self.num_of_peers):
            peers[i] = i
        return peers

    def set_peers_not_in_consensus(self):
        self.set_peers_not_in_consensus = True

    async def hard_apply_block(self, processing_results):
        self.hard_apply_block_called = True

    def is_next_block(self, previous_block):
        return previous_block == self.current_block

    def async_sleep(self, delay):
        tasks = asyncio.gather(
            asyncio.sleep(delay)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def add_solution(self, tx=None, tx_message=None, wallet=None, amount=None, to=None, receiver_wallet=None,
                     node_wallet=None, masternode=None, processing_results=None):

        masternode = masternode or Wallet()
        receiver_wallet = receiver_wallet or Wallet()
        node_wallet = node_wallet or Wallet()

        wallet = wallet or self.wallet
        amount = amount or "10.5"
        to = to or receiver_wallet.verifying_key

        if tx_message is None:
            transaction = tx or get_new_currency_tx(wallet=wallet, amount=amount, to=to)

        tx_message = tx_message or get_tx_message(tx=transaction, node_wallet=masternode)

        processing_results = get_processing_results(tx_message=tx_message, node_wallet=node_wallet)

        self.validation_queue.append(processing_results=processing_results)

        return processing_results

    def add_solutions(self, amount_of_solutions, tx=None, tx_message=None, amount=None, wallet=None, to=None,
                      receiver_wallet=None, masternode=None, node_wallets=[]
                      ):

        if len(node_wallets) is 0:
            for w in range(amount_of_solutions):
                node_wallets.append(Wallet())

        if masternode is None:
            masternode = node_wallets[0]

        receiver_wallet = receiver_wallet or Wallet()

        wallet = wallet or self.wallet
        amount = amount or "10.5"
        to = to or receiver_wallet.verifying_key

        if tx_message is None:
            transaction = tx or get_new_currency_tx(wallet=wallet, amount=amount, to=to)

        tx_message = tx_message or get_tx_message(tx=transaction, node_wallet=masternode)

        processing_results = []

        for a in range(amount_of_solutions):
            if tx is None:
                processing_results.append(
                    self.add_solution(tx_message=tx_message, node_wallet=node_wallets[a])
                )

        return processing_results

    def alter_result(self, hlc_timestamp, node_vk, new_result):
        results = self.validation_queue.validation_results.get(hlc_timestamp, None)
        if results is None:
            return

        old_result = results['solutions'][node_vk]
        results['solutions'][node_vk] = new_result
        old_lookup = results['result_lookup'].get(old_result, None)

        if old_lookup is not None:
            results['result_lookup'][new_result] = old_lookup
            del results['result_lookup'][old_result]

    def process_next(self):
        # Run process next, no consensus should be met as ideal is still possible
        tasks = asyncio.gather(
            self.validation_queue.process_next()
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def test_get_solution_exists(self):
        node_wallet = Wallet()
        processing_results = self.add_solution(node_wallet=node_wallet)

        solution = self.validation_queue.get_result_hash_for_vk(
            hlc_timestamp=processing_results['hlc_timestamp'],
            node_vk=node_wallet.verifying_key
        )

        self.assertIsNotNone(solution)

    def test_get_solution_hlc_DOES_NOT_exist(self):
        node_wallet = Wallet()
        self.add_solution(node_wallet=node_wallet)

        self.hlc_clock.get_new_hlc_timestamp()

        solution = self.validation_queue.get_result_hash_for_vk(
            hlc_timestamp=self.hlc_clock.get_new_hlc_timestamp(),
            node_vk=node_wallet.verifying_key
        )
        self.assertIsNone(solution)

    def test_get_solution_nodevk_DOES_NOT_exist(self):
        node_wallet = Wallet()
        processing_results = self.add_solution(node_wallet=node_wallet)

        solution = self.validation_queue.get_result_hash_for_vk(
            hlc_timestamp=processing_results['hlc_timestamp'],
            node_vk=Wallet().verifying_key
        )

        self.assertIsNone(solution)

    def test_append(self):
        # These are solutions from me
        receiver_wallet = Wallet()
        node_wallet = Wallet()

        transaction = get_new_currency_tx(wallet=self.wallet, amount="10.5", to=receiver_wallet.verifying_key)
        tx_message = get_tx_message(tx=transaction, node_wallet=node_wallet)
        processing_results = get_processing_results(tx_message=tx_message, node_wallet=node_wallet)

        hlc_timestamp = tx_message['hlc_timestamp']

        self.validation_queue.append(
            processing_results=processing_results
        )

        result_hash = self.validation_queue.get_result_hash_for_vk(
            hlc_timestamp=hlc_timestamp,
            node_vk=node_wallet.verifying_key
        )

        self.assertEqual(result_hash, processing_results['proof']['tx_result_hash'])

        self.assertEqual(len(self.validation_queue), 1)
        self.assertEqual(self.validation_queue[0], hlc_timestamp)

    def test_append_update(self):
        # These are solutions from me
        node_wallet_1 = Wallet()
        node_wallet_2 = Wallet()

        processing_results_1, processing_results_2 = self.add_solutions(
            amount_of_solutions=2,
            node_wallets=[node_wallet_1, node_wallet_2]
        )

        hlc_timestamp = processing_results_1['hlc_timestamp']

        self.validation_queue.append(processing_results=processing_results_1)
        self.validation_queue.append(processing_results=processing_results_2)

        node_wallet_1_solution = self.validation_queue.get_result_hash_for_vk(
            hlc_timestamp=hlc_timestamp,
            node_vk=node_wallet_1.verifying_key
        )
        node_wallet_2_solution = self.validation_queue.get_result_hash_for_vk(
            hlc_timestamp=hlc_timestamp,
            node_vk=node_wallet_2.verifying_key
        )

        self.assertEqual(node_wallet_1_solution, processing_results_1['proof']['tx_result_hash'])
        self.assertEqual(node_wallet_2_solution, processing_results_2['proof']['tx_result_hash'])

        self.assertEqual(len(self.validation_queue), 1)
        self.assertEqual(self.validation_queue[0], hlc_timestamp)

    # Disabled test case for now because we might now accept earlier HLCs
    '''
    def test_append_ignore_older_than_consensus(self):
        # These are solutions from peers
        # Updated stored solution for a peer when update is received

        self.validation_queue.last_hlc_in_consensus = "2"
        hlc_timestamp = "1"
        peer_wallet = Wallet()

        # Add a peer solution
        self.add_solution(
            verifying_key=peer_wallet.verifying_key,
            hlc_timestamp=hlc_timestamp,
            hash="1"
        )

        solution = self.validation_queue.get_solution(
            hlc_timestamp=hlc_timestamp,
            node_vk=peer_wallet.verifying_key
        )

        self.assertIsNone(solution)
    '''
    def test_awaiting_validation(self):
        receiver_wallet = Wallet()
        node_wallet = Wallet()
        tx_message = get_tx_message(wallet=self.wallet, amount="10.5", to=receiver_wallet.verifying_key)
        processing_results = get_processing_results(tx_message=tx_message, node_wallet=node_wallet)

        hlc_timestamp = tx_message['hlc_timestamp']
        self.validation_queue.append(processing_results=processing_results)

        self.assertTrue(self.validation_queue.awaiting_validation(hlc_timestamp=hlc_timestamp))

        self.assertIsNotNone(self.validation_queue.validation_results[hlc_timestamp]['solutions'][node_wallet.verifying_key])

    def test_get_consensus_results(self):
        node_wallet_1 = Wallet()
        node_wallet_2 = Wallet()

        processing_results_1, processing_results_2 = self.add_solutions(
            amount_of_solutions=2,
            node_wallets=[node_wallet_1, node_wallet_2]
        )

        hlc_timestamp = processing_results_1['hlc_timestamp']

        self.validation_queue.process(hlc_timestamp=hlc_timestamp)

        consensus_result = self.validation_queue.get_consensus_results(
            hlc_timestamp=hlc_timestamp
        )
        self.assertIsNotNone(consensus_result)

    def test_process_next_not_enough_solutions_to_attempt_consensus(self):
        self.add_solution()

        self.num_of_peers = 1  # Does not include me

        # Await the the queue attempting consensus
        self.process_next()

        self.assertFalse(self.hard_apply_block_called)
        self.assertEqual(self.validation_queue.last_hlc_in_consensus, "")

    def test_process_ideal_consensus(self):
        node_wallet_1 = self.wallet
        node_wallet_2 = Wallet()

        processing_results_1, processing_results_2 = self.add_solutions(
            amount_of_solutions=2,
            node_wallets=[node_wallet_1, node_wallet_2],
            masternode=node_wallet_1
        )

        hlc_timestamp = processing_results_1['hlc_timestamp']

        self.num_of_peers = 1  # Does not include me

        # Await the the queue attempting consensus
        self.process_next()

        self.assertTrue(self.hard_apply_block_called)
        self.assertEqual(self.validation_queue.last_hlc_in_consensus, hlc_timestamp)
        self.assertIsNone(self.validation_queue.validation_results.get(hlc_timestamp))

    def test_process_next_ideal_consensus_on_updated_information_from_me(self):
        self.num_of_peers = 2  # Does not include me

        node_wallet_1 = self.wallet
        node_wallet_2 = Wallet()
        receiver_wallet = Wallet()

        tx_info = {
            'wallet': node_wallet_1,
            'amount': 100.5,
            'to': receiver_wallet.verifying_key
        }

        transaction = get_new_currency_tx(**tx_info)
        tx_message = get_tx_message(tx=transaction, node_wallet=node_wallet_1)

        hlc_timestamp = tx_message['hlc_timestamp']

        # Add a bad tx_result for this node
        tx_message_bad = deepcopy(tx_message)
        tx_message_bad['tx']['payload']['kwargs']['to'] = 'testing_vk'
        processing_results_1_bad = self.add_solution(
            tx_message=tx_message_bad,
            node_wallet=node_wallet_1
        )

        # Add a good result from another node
        processing_results_2 = self.add_solution(
            tx_message=tx_message,
            node_wallet=node_wallet_2
        )

        # Process consensus
        self.process_next()

        # Verify consensus is FALSE
        self.assertFalse(self.validation_queue.validation_results[hlc_timestamp]['last_check_info']['has_consensus'])
        self.assertFalse(self.validation_queue.validation_results[hlc_timestamp]['last_consensus_result']['has_consensus'])


        # Add proper solution for this node

        processing_results_1_good = self.add_solution(
            tx_message=tx_message,
            node_wallet=node_wallet_1
        )

        # Process consensus
        self.process_next()

        # Verify consensus is TRUE
        self.assertEqual(hlc_timestamp, self.validation_queue.last_hlc_in_consensus)
        self.assertTrue(self.hard_apply_block_called)

    def test_process_next_ideal_consensus_on_updated_information_from_peer(self):
        self.num_of_peers = 2  # Does not include me

        node_wallet_1 = self.wallet
        node_wallet_2 = Wallet()
        receiver_wallet = Wallet()

        tx_info = {
            'wallet': node_wallet_1,
            'amount': 100.5,
            'to': receiver_wallet.verifying_key
        }

        transaction = get_new_currency_tx(**tx_info)
        tx_message = get_tx_message(tx=transaction, node_wallet=node_wallet_1)

        hlc_timestamp = tx_message['hlc_timestamp']

        # Add a bad tx_result for this node
        tx_message_bad = deepcopy(tx_message)
        tx_message_bad['tx']['payload']['kwargs']['to'] = 'testing_vk'
        processing_results_1 = self.add_solution(
            tx_message=tx_message,
            node_wallet=node_wallet_1
        )

        # Add a good result from another node
        processing_results_2_bad = self.add_solution(
            tx_message=tx_message_bad,
            node_wallet=node_wallet_2
        )

        # Process consensus
        self.process_next()

        # Verify consensus is FALSE
        self.assertFalse(self.validation_queue.validation_results[hlc_timestamp]['last_check_info']['has_consensus'])
        self.assertFalse(self.validation_queue.validation_results[hlc_timestamp]['last_consensus_result']['has_consensus'])


        # Add proper solution for this node

        processing_results_2_good = self.add_solution(
            tx_message=tx_message,
            node_wallet=node_wallet_2
        )

        # Process consensus
        self.process_next()

        # Verify consensus is TRUE
        self.assertEqual(hlc_timestamp, self.validation_queue.last_hlc_in_consensus)
        self.assertTrue(self.hard_apply_block_called)

    def test_process_next_ideal_consensus_matches_me(self):
        '''
            Ideal consensus test setup will have 2 nodes both of which are in consensus
            I will be one of the 2 nodes in the consensus group so I should hard apply and move on
        '''

        self.num_of_peers = 1

        node_wallet_1 = self.wallet
        node_wallet_2 = Wallet()

        processing_results_1, processing_results_2 = self.add_solutions(
            amount_of_solutions=2,
            node_wallets=[node_wallet_1, node_wallet_2],
            masternode=node_wallet_1
        )

        hlc_timestamp = processing_results_1['hlc_timestamp']

        self.process_next()

        # Test that consensus was achieved and we are in it
        # Hard apply was called
        self.assertTrue(self.hard_apply_block_called)
        # hlc_timestamp was marked as last_hlc_in_consensus
        self.assertEqual(self.validation_queue.last_hlc_in_consensus, hlc_timestamp)
        # All results deleted from validation_results object
        self.assertIsNone(self.validation_queue.validation_results.get(hlc_timestamp))

    def test_process_next_ideal_consensus_DOES_NOT_match_me(self):
        '''
            Ideal consensus test setup will have 2 nodes both of which are in consensus
            I will be one of the 2 nodes in the consensus group so I should hard apply and move on
        '''

        self.num_of_peers = 2

        node_wallet_1 = self.wallet
        node_wallet_2 = Wallet()
        node_wallet_3 = Wallet()
        receiver_wallet = Wallet()

        tx_info = {
            'wallet': node_wallet_1,
            'amount': 100.5,
            'to': receiver_wallet.verifying_key
        }

        transaction = get_new_currency_tx(**tx_info)
        tx_message = get_tx_message(tx=transaction, node_wallet=node_wallet_1)

        # Add our solution (which is bad)
        tx_message_bad = deepcopy(tx_message)
        tx_message_bad['tx']['payload']['kwargs']['to'] = 'testing_vk'
        processing_results_1 = self.add_solution(
            tx_message=tx_message_bad,
            node_wallet=node_wallet_1
        )

        # Add good solutions from other nodes
        processing_results_2, processing_results_3 = self.add_solutions(
            amount_of_solutions=2,
            tx_message=tx_message,
            node_wallets=[node_wallet_2, node_wallet_3],
            masternode=node_wallet_1
        )

        hlc_timestamp = processing_results_1['hlc_timestamp']

        self.process_next()

        # Hard apply was called
        self.assertTrue(self.hard_apply_block_called)
        # hlc_timestamp was marked as last_hlc_in_consensus
        self.assertEqual(hlc_timestamp, self.validation_queue.last_hlc_in_consensus)
        # All results deleted from validation_results object
        self.assertIsNone(self.validation_queue.validation_results.get(hlc_timestamp))

    def test_process_ideal_consensus_MISSING_me(self):
        '''
            Ideal consensus test setup will have 3 nodes two in consensus and I will not provide a solution
            Consensus should still conclude even though I don't provide a solution.
        '''
        self.num_of_peers = 2

        node_wallet_1 = Wallet()
        node_wallet_2 = Wallet()

        # Add matching solutions from other nodes
        processing_results_1, processing_results_2 = self.add_solutions(
            amount_of_solutions=2,
            node_wallets=[node_wallet_1, node_wallet_2],
            masternode=self.wallet
        )

        hlc_timestamp = processing_results_1['hlc_timestamp']

        self.process_next()

        # Hard apply was called
        self.assertTrue(self.hard_apply_block_called)

        # hlc_timestamp was marked as last_hlc_in_consensus
        self.assertEqual(hlc_timestamp, self.validation_queue.last_hlc_in_consensus)
        # All results deleted from validation_results object
        self.assertIsNone(self.validation_queue.validation_results.get(hlc_timestamp))

    def test_process_next_eager_consensus_matches_me(self):
        '''
            Eager consensus test setup will have 4 nodes. Two are in consensus and the other two differ from consensus
            and each other.
            This is a 50% consensus and the validation queue should decide on eager consensus only when all 4 results
            are in.
            I will be in the consensus group so I should hard apply and move on
        '''

        self.num_of_peers = 3  # Does not include me

        node_wallet_1 = self.wallet
        node_wallet_2 = Wallet()
        node_wallet_3 = Wallet()
        node_wallet_4 = Wallet()
        receiver_wallet = Wallet()

        tx_info = {
            'wallet': node_wallet_1,
            'amount': 100.5,
            'to': receiver_wallet.verifying_key
        }

        transaction = get_new_currency_tx(**tx_info)
        tx_message = get_tx_message(tx=transaction, node_wallet=node_wallet_1)

        hlc_timestamp = tx_message['hlc_timestamp']

        # Add good results in which I am a part of
        processing_results_1, processing_results_2 = self.add_solutions(
            amount_of_solutions=2,
            tx_message=tx_message,
            node_wallets=[node_wallet_1, node_wallet_2],
            masternode=self.wallet
        )

        # Add 1 bad tx_result from node 3
        tx_message_bad_1 = deepcopy(tx_message)
        tx_message_bad_1['tx']['payload']['kwargs']['to'] = 'testing_vk_1'
        processing_results_3 = self.add_solution(
            tx_message=tx_message_bad_1,
            node_wallet=node_wallet_3,
            masternode=node_wallet_1
        )

        # Run process next, no consensus should be met as ideal is still possible
        self.process_next()

        # Make sure consensus wasn't reached
        self.assertFalse(self.hard_apply_block_called)

        self.assertEqual(self.validation_queue.last_hlc_in_consensus, "")
        # Make sure ideal consensus is still possible
        self.assertTrue(self.validation_queue.check_ideal_consensus_possible(hlc_timestamp))

        # Add 1 bad tx_result from node 4
        tx_message_bad_2 = deepcopy(tx_message)
        tx_message_bad_2['tx']['payload']['kwargs']['to'] = 'testing_vk_2'

        processing_results_4 = self.add_solution(
            tx_message=tx_message_bad_2,
            node_wallet=node_wallet_4,
            masternode=node_wallet_1
        )

        # Run process next. All peers are in and only 50% are in consensus. Eager consensus is expected
        self.assertEqual(4, self.validation_queue.check_num_of_solutions(hlc_timestamp))
        self.process_next()

        # validation queue should process consensus
        # hard apply is called
        self.assertTrue(self.hard_apply_block_called)

        # hlc_timestamp is marked as last_hlc_in_consensus
        self.assertEqual(self.validation_queue.last_hlc_in_consensus, hlc_timestamp)
        # all results are deleted from the validation_results object
        self.assertIsNone(self.validation_queue.validation_results.get(hlc_timestamp))

    def test_process_next_eager_consensus_DOES_NOT_match_me(self):
        '''
            Eager consensus test setup will have 4 nodes. Two are in consensus and the other two differ from consensus
            and each other.
            This is a 50% consensus and the validation queue should decide on eager consensus only when all 4 results
            are in.
            I will be in the group that differs so I should attempt to rollback after eager consensus is determined
        '''
        '''
            Eager consensus test setup will have 4 nodes. Two are in consensus and the other two differ from consensus
            and each other.
            This is a 50% consensus and the validation queue should decide on eager consensus only when all 4 results
            are in.
            I will be in the consensus group so I should hard apply and move on
        '''

        self.num_of_peers = 3  # Does not include me

        node_wallet_1 = Wallet()
        node_wallet_2 = Wallet()
        node_wallet_3 = Wallet()
        node_wallet_4 = self.wallet
        receiver_wallet = Wallet()

        tx_info = {
            'wallet': node_wallet_1,
            'amount': 100.5,
            'to': receiver_wallet.verifying_key
        }

        transaction = get_new_currency_tx(**tx_info)
        tx_message = get_tx_message(tx=transaction, node_wallet=node_wallet_1)

        hlc_timestamp = tx_message['hlc_timestamp']

        # Add good results in which I am a part of
        processing_results_1, processing_results_2 = self.add_solutions(
            amount_of_solutions=2,
            tx_message=tx_message,
            node_wallets=[node_wallet_1, node_wallet_2],
            masternode=self.wallet
        )

        # Add 1 bad tx_result from node 3
        tx_message_bad_1 = deepcopy(tx_message)
        tx_message_bad_1['tx']['payload']['kwargs']['to'] = 'testing_vk_1'
        processing_results_3 = self.add_solution(
            tx_message=tx_message_bad_1,
            node_wallet=node_wallet_3,
            masternode=node_wallet_1
        )

        # Run process next, no consensus should be met as ideal is still possible
        self.process_next()

        # Make sure consensus wasn't reached
        self.assertFalse(self.hard_apply_block_called)
        self.assertEqual(self.validation_queue.last_hlc_in_consensus, "")
        # Make sure ideal consensus is still possible
        self.assertTrue(self.validation_queue.check_ideal_consensus_possible(hlc_timestamp))

        # Add 1 bad tx_result from node 4
        tx_message_bad_2 = deepcopy(tx_message)
        tx_message_bad_2['tx']['payload']['kwargs']['to'] = 'testing_vk_2'

        processing_results_4 = self.add_solution(
            tx_message=tx_message_bad_2,
            node_wallet=node_wallet_4,
            masternode=node_wallet_1
        )

        # Run process next. All peers are in and only 50% are in consensus. Eager consensus is expected
        self.assertEqual(4, self.validation_queue.check_num_of_solutions(hlc_timestamp))
        self.process_next()

        # validation queue should process consensus
        # hard apply is called
        self.assertTrue(self.hard_apply_block_called)

        # hlc_timestamp is marked as last_hlc_in_consensus
        self.assertEqual(self.validation_queue.last_hlc_in_consensus, hlc_timestamp)
        # all results are deleted from the validation_results object
        self.assertIsNone(self.validation_queue.validation_results.get(hlc_timestamp))

    def test_process_next_failed_consensus_matches_me(self):
        '''
            Failed consensus setup will have 3 nodes all with different solutions.
            I will have the top solution when determining higher numerical hex value.
            This one is tricky due to the way failed consensus is established which is to get the numerical value of
            the result hash. I will have to manually alter the results hashes to test this.
        '''
        self.num_of_peers = 2  # Does not include me

        node_wallet_1 = self.wallet
        node_wallet_2 = Wallet()
        node_wallet_3 = Wallet()
        receiver_wallet = Wallet()

        tx_info = {
            'wallet': node_wallet_1,
            'amount': 100.5,
            'to': receiver_wallet.verifying_key
        }

        transaction = get_new_currency_tx(**tx_info)
        tx_message = get_tx_message(tx=transaction, node_wallet=node_wallet_1)

        hlc_timestamp = tx_message['hlc_timestamp']

        # Add my solution
        processing_results_1 = self.add_solution(
            tx_message=tx_message,
            node_wallet=node_wallet_1,
            masternode=self.wallet
        )

        self.alter_result(hlc_timestamp=hlc_timestamp, node_vk=node_wallet_1.verifying_key, new_result="1")

        # Add another solution from Node 2
        tx_message_bad_1 = deepcopy(tx_message)
        tx_message_bad_1['tx']['payload']['kwargs']['to'] = 'testing_vk_1'
        processing_results_2 = self.add_solution(
            tx_message=tx_message_bad_1,
            node_wallet=node_wallet_2,
            masternode=node_wallet_1
        )

        self.alter_result(hlc_timestamp=hlc_timestamp, node_vk=node_wallet_2.verifying_key, new_result="2")

        # Add another solution from Node 3
        tx_message_bad_2 = deepcopy(tx_message)
        tx_message_bad_2['tx']['payload']['kwargs']['to'] = 'testing_vk_2'

        processing_results_3 = self.add_solution(
            tx_message=tx_message_bad_2,
            node_wallet=node_wallet_3,
            masternode=node_wallet_1
        )

        self.alter_result(hlc_timestamp=hlc_timestamp, node_vk=node_wallet_3.verifying_key, new_result="3")

        # Run process next. All peers are in and only 50% are in consensus. Eager consensus is expected
        self.assertEqual(3, self.validation_queue.check_num_of_solutions(hlc_timestamp))
        self.process_next()

        # validation queue should process consensus
        # hard apply is called
        self.assertTrue(self.hard_apply_block_called)

        # hlc_timestamp is marked as last_hlc_in_consensus
        self.assertEqual(self.validation_queue.last_hlc_in_consensus, hlc_timestamp)
        # all results are deleted from the validation_results object
        self.assertIsNone(self.validation_queue.validation_results.get(hlc_timestamp))

    def test_process_next_failed_consensus_DOES_NOT_match_me(self):
        '''
            Failed consensus setup will have 3 nodes all with different solutions.
            I will NOT have the top solution when determining higher numerical hex value
        '''
        self.num_of_peers = 2  # Does not include me

        node_wallet_1 = Wallet()
        node_wallet_2 = Wallet()
        node_wallet_3 = self.wallet
        receiver_wallet = Wallet()

        tx_info = {
            'wallet': node_wallet_1,
            'amount': 100.5,
            'to': receiver_wallet.verifying_key
        }

        transaction = get_new_currency_tx(**tx_info)
        tx_message = get_tx_message(tx=transaction, node_wallet=node_wallet_1)

        hlc_timestamp = tx_message['hlc_timestamp']

        # Add my solution
        processing_results_1 = self.add_solution(
            tx_message=tx_message,
            node_wallet=node_wallet_1,
            masternode=self.wallet
        )

        self.alter_result(hlc_timestamp=hlc_timestamp, node_vk=node_wallet_1.verifying_key, new_result="1")

        # Add another solution from Node 2
        tx_message_bad_1 = deepcopy(tx_message)
        tx_message_bad_1['tx']['payload']['kwargs']['to'] = 'testing_vk_1'
        processing_results_2 = self.add_solution(
            tx_message=tx_message_bad_1,
            node_wallet=node_wallet_2,
            masternode=node_wallet_1
        )

        self.alter_result(hlc_timestamp=hlc_timestamp, node_vk=node_wallet_2.verifying_key, new_result="2")

        # Add another solution from Node 3
        tx_message_bad_2 = deepcopy(tx_message)
        tx_message_bad_2['tx']['payload']['kwargs']['to'] = 'testing_vk_2'

        processing_results_3 = self.add_solution(
            tx_message=tx_message_bad_2,
            node_wallet=node_wallet_3,
            masternode=node_wallet_1
        )

        self.alter_result(hlc_timestamp=hlc_timestamp, node_vk=node_wallet_3.verifying_key, new_result="3")

        # Run process next. All peers are in and only 50% are in consensus. Eager consensus is expected
        self.assertEqual(3, self.validation_queue.check_num_of_solutions(hlc_timestamp))
        self.process_next()

        # validation queue should process consensus
        # hard apply is called
        self.assertTrue(self.hard_apply_block_called)

        # hlc_timestamp is marked as last_hlc_in_consensus
        self.assertEqual(self.validation_queue.last_hlc_in_consensus, hlc_timestamp)
        # all results are deleted from the validation_results object
        self.assertIsNone(self.validation_queue.validation_results.get(hlc_timestamp))

    def test_process_fall_through_from_ideal_to_failure(self):
        '''
            This test will add results and process after each one. Making sure the validation queue can switch between
            the consensus types as new info comes in.
            Failed consensus setup will have 4 and they will tie for consensus and that will not be known till the 4th
            result comes in.
            I will NOT have the top solution when determining higher numerical hex value
        '''
        self.num_of_peers = 3  # Does not include me

        node_wallet_1 = Wallet()
        node_wallet_2 = Wallet()
        node_wallet_3 = Wallet()
        node_wallet_4 = self.wallet
        receiver_wallet = Wallet()

        tx_info = {
            'wallet': node_wallet_1,
            'amount': 100.5,
            'to': receiver_wallet.verifying_key
        }

        transaction = get_new_currency_tx(**tx_info)
        tx_message = get_tx_message(tx=transaction, node_wallet=node_wallet_1)

        hlc_timestamp = tx_message['hlc_timestamp']

        # Add my solution
        self.add_solution(
            tx_message=tx_message,
            node_wallet=node_wallet_1,
            masternode=self.wallet
        )
        self.alter_result(hlc_timestamp=hlc_timestamp, node_vk=node_wallet_1.verifying_key, new_result="1")

        self.process_next()
        self.assertTrue(self.validation_queue.check_ideal_consensus_possible(hlc_timestamp))
        self.assertTrue(self.validation_queue.check_eager_consensus_possible(hlc_timestamp))

        # Add 2 of 4 results to the validation results object and process next
        # Add another solution from Node 3
        tx_message_bad = deepcopy(tx_message)
        tx_message_bad['tx']['payload']['kwargs']['to'] = 'testing_vk_1'

        self.add_solution(
            tx_message=tx_message_bad,
            node_wallet=node_wallet_2,
            masternode=node_wallet_1
        )

        self.alter_result(hlc_timestamp=hlc_timestamp, node_vk=node_wallet_2.verifying_key, new_result="2")

        self.process_next()
        self.assertTrue(self.validation_queue.check_ideal_consensus_possible(hlc_timestamp))
        self.assertTrue(self.validation_queue.check_eager_consensus_possible(hlc_timestamp))

        # Add 3 of 4 results to the validation results object and process next
        self.add_solution(
            tx_message=tx_message,
            node_wallet=node_wallet_3,
            masternode=node_wallet_1
        )

        self.alter_result(hlc_timestamp=hlc_timestamp, node_vk=node_wallet_3.verifying_key, new_result="1")

        self.process_next()
        self.assertTrue(self.validation_queue.check_ideal_consensus_possible(hlc_timestamp))
        self.assertTrue(self.validation_queue.check_eager_consensus_possible(hlc_timestamp))

        # Add 4 of 4 results to the validation results object and process next
        self.add_solution(
            tx_message=tx_message_bad,
            node_wallet=node_wallet_4,
            masternode=node_wallet_1
        )

        self.alter_result(hlc_timestamp=hlc_timestamp, node_vk=node_wallet_4.verifying_key, new_result="2")

        self.assertEqual(4, self.validation_queue.check_num_of_solutions(hlc_timestamp))

        self.process_next()

        self.assertFalse(self.validation_queue.check_ideal_consensus_possible(hlc_timestamp))
        self.assertFalse(self.validation_queue.check_eager_consensus_possible(hlc_timestamp))

        # hard apply is called
        self.assertTrue(self.hard_apply_block_called)

    def test_tally_solutions(self):
        self.num_of_peers = 5  # Does not include me

        tx_info = {
            'wallet': self.wallet,
            'amount': 100.5,
            'to': Wallet().verifying_key
        }

        transaction = get_new_currency_tx(**tx_info)
        tx_message = get_tx_message(tx=transaction, node_wallet=self.wallet)

        hlc_timestamp = tx_message['hlc_timestamp']

        # Add my solution
        self.add_solution(
            tx_message=tx_message,
            node_wallet=self.wallet,
            masternode=self.wallet
        )
        self.alter_result(hlc_timestamp=hlc_timestamp, node_vk=self.wallet.verifying_key, new_result="1")

        # Add some nodes with another result
        tx_message_bad_1 = deepcopy(tx_message)
        tx_message_bad_1['tx']['payload']['kwargs']['to'] = 'testing_vk_1'
        node_wallets_2 = [Wallet(), Wallet()]
        self.add_solutions(
            amount_of_solutions=2,
            node_wallets=node_wallets_2,
            tx_message=tx_message_bad_1,
            masternode=self.wallet
        )
        self.alter_result(hlc_timestamp=hlc_timestamp, node_vk=node_wallets_2[0].verifying_key, new_result="2")
        self.alter_result(hlc_timestamp=hlc_timestamp, node_vk=node_wallets_2[1].verifying_key, new_result="2")

        # Add some more nodes with another result
        tx_message_bad_2 = deepcopy(tx_message)
        tx_message_bad_2['tx']['payload']['kwargs']['to'] = 'testing_vk_2'

        node_wallets_3 = [Wallet(), Wallet(), Wallet()]
        self.add_solutions(
            amount_of_solutions=3,
            node_wallets=node_wallets_3,
            tx_message=tx_message_bad_2,
            masternode=self.wallet
        )
        self.alter_result(hlc_timestamp=hlc_timestamp, node_vk=node_wallets_3[0].verifying_key, new_result="3")
        self.alter_result(hlc_timestamp=hlc_timestamp, node_vk=node_wallets_3[1].verifying_key, new_result="3")
        self.alter_result(hlc_timestamp=hlc_timestamp, node_vk=node_wallets_3[2].verifying_key, new_result="3")

        tally = self.validation_queue.tally_solutions(
            solutions=self.validation_queue.validation_results[hlc_timestamp]['solutions']
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
        self.num_of_peers = 4  # Does not include me

        tx_info = {
            'wallet': self.wallet,
            'amount': 100.5,
            'to': Wallet().verifying_key
        }

        transaction = get_new_currency_tx(**tx_info)
        tx_message = get_tx_message(tx=transaction, node_wallet=self.wallet)

        hlc_timestamp = tx_message['hlc_timestamp']

        # Add my solution
        self.add_solution(
            tx_message=tx_message,
            node_wallet=self.wallet,
            masternode=self.wallet
        )
        self.alter_result(hlc_timestamp=hlc_timestamp, node_vk=self.wallet.verifying_key, new_result="1")

        # Add some nodes with another result
        tx_message_bad_1 = deepcopy(tx_message)
        tx_message_bad_1['tx']['payload']['kwargs']['to'] = 'testing_vk_1'
        node_wallets_2 = [Wallet(), Wallet()]
        self.add_solutions(
            amount_of_solutions=2,
            node_wallets=node_wallets_2,
            tx_message=tx_message_bad_1,
            masternode=self.wallet
        )
        self.alter_result(hlc_timestamp=hlc_timestamp, node_vk=node_wallets_2[0].verifying_key, new_result="2")
        self.alter_result(hlc_timestamp=hlc_timestamp, node_vk=node_wallets_2[1].verifying_key, new_result="2")

        # Add some more nodes with another result
        tx_message_bad_2 = deepcopy(tx_message)
        tx_message_bad_2['tx']['payload']['kwargs']['to'] = 'testing_vk_2'

        node_wallets_3 = [Wallet(), Wallet()]
        self.add_solutions(
            amount_of_solutions=2,
            node_wallets=node_wallets_3,
            tx_message=tx_message_bad_2,
            masternode=self.wallet
        )
        self.alter_result(hlc_timestamp=hlc_timestamp, node_vk=node_wallets_3[0].verifying_key, new_result="3")
        self.alter_result(hlc_timestamp=hlc_timestamp, node_vk=node_wallets_3[1].verifying_key, new_result="3")

        tally = self.validation_queue.tally_solutions(
            solutions=self.validation_queue.validation_results[hlc_timestamp]['solutions']
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

        ideal_consensus_results = self.validation_queue.check_ideal_consensus(
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

        ideal_consensus_results = self.validation_queue.check_ideal_consensus(
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

        ideal_consensus_results = self.validation_queue.check_ideal_consensus(
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

        ideal_consensus_results = self.validation_queue.check_ideal_consensus(
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

        eager_consensus_results = self.validation_queue.check_eager_consensus(
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

        eager_consensus_results = self.validation_queue.check_eager_consensus(
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

        eager_consensus_results = self.validation_queue.check_eager_consensus(
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

        eager_consensus_results = self.validation_queue.check_eager_consensus(
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

        failed_consensus_results = self.validation_queue.check_failed_consensus(
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

        failed_consensus_results = self.validation_queue.check_failed_consensus(
            tally_info=tally_info,
            consensus_needed=consensus_needed,
            my_solution="2"
        )

        self.assertFalse(failed_consensus_results['matches_me'])
        self.assertTrue(failed_consensus_results['has_consensus'])
        self.assertEqual('failed', failed_consensus_results['consensus_type'])
        self.assertEqual('1', failed_consensus_results['solution'])
        self.assertEqual('2', failed_consensus_results['my_solution'])

    def test_clear_my_solutions(self):
        self.validation_queue.validation_results = {
            'hlc_1': {
                'solutions': {
                    self.validation_queue.wallet.verifying_key: 'solution',
                    '2': 'solution'
                }
            },
            'hlc_2': {
                'solutions': {
                    self.validation_queue.wallet.verifying_key: 'solution'
                }
            },
            'hlc_3': {
                'solutions': {
                    '2': 'solution'
                }
            }
            ,
            'hlc_4': {
                'solutions': {}
            }
        }
        self.validation_queue.clear_my_solutions()

        self.assertIsNone(self.validation_queue.validation_results['hlc_1']['solutions'].get(self.validation_queue.wallet.verifying_key))
        self.assertIsNotNone(self.validation_queue.validation_results['hlc_1']['solutions'].get('2'))

        self.assertIsNone(self.validation_queue.validation_results['hlc_2']['solutions'].get(self.validation_queue.wallet.verifying_key))

        self.assertIsNone(self.validation_queue.validation_results['hlc_3']['solutions'].get(self.validation_queue.wallet.verifying_key))
        self.assertIsNotNone(self.validation_queue.validation_results['hlc_3']['solutions'].get('2'))

    def test_get_get_processed_transaction(self):
        node_wallet_1 = Wallet()
        node_wallet_2 = Wallet()

        processing_results_1, processing_results_2 = self.add_solutions(
            amount_of_solutions=2,
            node_wallets=[node_wallet_1, node_wallet_2]
        )

        hlc_timestamp = processing_results_1['hlc_timestamp']

        processed_transaction = self.validation_queue.get_processed_transaction(
            hlc_timestamp=hlc_timestamp
        )
        self.assertIsNotNone(processed_transaction)

    def test_get_proofs_from_results(self):
        self.num_of_peers = 2

        node_wallet_1 = Wallet()
        node_wallet_2 = Wallet()

        processing_results_1, processing_results_2 = self.add_solutions(
            amount_of_solutions=2,
            node_wallets=[node_wallet_1, node_wallet_2]
        )

        tx_result_hash = processing_results_1['proof'].get('tx_result_hash')
        hlc_timestamp = processing_results_1['hlc_timestamp']

        # Mock that the hlc has consensus, so the method will gather the proofs
        self.validation_queue.validation_results[hlc_timestamp]['last_consensus_result'] = {
            'has_consensus': True,
            'matches_me': True,
            'solution': tx_result_hash
        }

        proofs = self.validation_queue.get_proofs_from_results(hlc_timestamp=hlc_timestamp)

        self.assertEqual(2, len(proofs))