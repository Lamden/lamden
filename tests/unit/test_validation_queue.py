from unittest import TestCase
from contracting.db.driver import ContractDriver
from lamden.nodes import validation_queue
from lamden.crypto.wallet import Wallet
from lamden.nodes.hlc import HLC_Clock
from lamden.network import Network
from copy import deepcopy
from lamden.crypto.canonical import tx_result_hash_from_tx_result_object
from tests.unit.helpers.mock_transactions import get_new_currency_tx, get_tx_message, get_processing_results
import asyncio
from lamden import storage

class TestValidationQueue(TestCase):
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

        network = Network(
            wallet=Wallet(),
            socket_base='tcp://127.0.0.1',
            testing=True,
            debug=True
        )

        self.validation_queue = validation_queue.ValidationQueue(
            wallet=self.wallet,
            consensus_percent=lambda: self.consensus_percent,
            hard_apply_block=self.hard_apply_block,
            stop_node=self.stop,
            testing=True,
            network=network,
            state=storage.StateManager()
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

        tx_result_hash = tx_result_hash_from_tx_result_object(tx_result=processing_results['tx_result'],
                                                              hlc_timestamp=hlc_timestamp)

        self.assertEqual(result_hash, tx_result_hash)

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

        tx_result_hash_1 = tx_result_hash_from_tx_result_object(
            tx_result=processing_results_1['tx_result'],
            hlc_timestamp=processing_results_1['hlc_timestamp']
        )
        tx_result_hash_2 = tx_result_hash_from_tx_result_object(
            tx_result=processing_results_2['tx_result'],
            hlc_timestamp=processing_results_2['hlc_timestamp']
        )

        self.assertEqual(node_wallet_1_solution, tx_result_hash_1)
        self.assertEqual(node_wallet_2_solution, tx_result_hash_2)

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

        processed_transaction = self.validation_queue.validation_results.get(hlc_timestamp)
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
        self.validation_queue.validation_results[hlc_timestamp]['last_check_info'] = {
            'has_consensus': True,
            'matches_me': True,
            'solution': tx_result_hash
        }

        proofs = self.validation_queue.get_proofs_from_results(hlc_timestamp=hlc_timestamp)

        self.assertEqual(2, len(proofs))