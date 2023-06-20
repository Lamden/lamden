from unittest import TestCase
from contracting.db.driver import ContractDriver, InMemDriver
from lamden.nodes import validation_queue
from lamden.crypto.wallet import Wallet
from lamden.nodes.hlc import HLC_Clock

from lamden.crypto.canonical import tx_result_hash_from_tx_result_object
from tests.unit.helpers.mock_transactions import get_new_currency_tx, get_tx_message, get_processing_results, get_new_processing_result
import asyncio
import hashlib
from contracting.db.encoder import encode

from lamden.utils.hlc import nanos_from_hlc_timestamp
from pathlib import Path
from lamden.storage import BlockStorage
import shutil

class TestValidationQueue(TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.wallet = Wallet()

        self.driver = ContractDriver(driver=InMemDriver())
        self.driver.set(
            key='rewards.S:value',
            value=(0.44, 0.44, 0.01, 0.01, 0.01)
        )

        self.hlc_clock = HLC_Clock()

        self.running = True

        self.consensus_percent = 51
        self.num_of_peers = 0

        self.hard_apply_block_called = False
        self.num_times_hard_apply_block_called = 0
        self.set_peers_not_in_consensus_called = False

        self.current_block = 64 * f'0'

        self.current_path = Path.cwd()
        self.temp_storage_dir = Path(f'{self.current_path}/temp_storage')
        if self.temp_storage_dir.is_dir():
            shutil.rmtree(self.temp_storage_dir)

        node_dir = Path(f'{self.temp_storage_dir}/{self.wallet.verifying_key}')
        block_storage = BlockStorage(root=node_dir)

        self.validation_queue = validation_queue.ValidationQueue(
            driver=self.driver,
            wallet=self.wallet,
            consensus_percent=lambda: self.consensus_percent,
            hard_apply_block=self.hard_apply_block,
            stop_node=self.stop,
            testing=True,
            get_block_by_hlc=self.get_block_by_hlc,
            get_block_from_network=self.get_block_from_network,
            blocks=block_storage
        )

        self.validation_queue.get_peers_for_consensus = self.get_peers_for_consensus
        self.validation_queue.multiprocess_consensus.get_peers_for_consensus = self.get_peers_for_consensus

        self.block = None
        self.get_block_by_hlc_called = False

        print("\n")

    def tearDown(self):
        self.validation_queue.stop()
        self.validation_queue.flush()
        if self.temp_storage_dir.is_dir():
            shutil.rmtree(self.temp_storage_dir)

        try:
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.close()
        except RuntimeError:
            pass

    def stop(self):
        self.running = False

    def get_block_by_hlc(self, hlc_timestamp):
        self.get_block_by_hlc_called = True
        return self.block

    async def get_block_from_network(self, hlc_timestamp):
        blocks = []
        for i in range(5):
            blocks.append({
                'hash': hlc_timestamp,
                'hlc_timestamp': hlc_timestamp,
                'number': nanos_from_hlc_timestamp(hlc_timestamp=hlc_timestamp)
            })
        return blocks

    async def stop_all_queues(self):
        return

    def start_all_queues(self):
        return

    def get_peers_for_consensus(self):
        peers = {}
        for i in range(self.num_of_peers + 1):
            peers[i] = i
        return peers

    def set_peers_not_in_consensus(self):
        self.set_peers_not_in_consensus = True

    async def hard_apply_block(self, processing_results=None, block=None):
        self.hard_apply_block_called = True
        self.num_times_hard_apply_block_called += 1

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

        processing_results = get_processing_results(driver=self.driver, tx_message=tx_message, node_wallet=node_wallet)

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
            self.validation_queue.process_all()
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def check_all(self):
        tasks = asyncio.gather(
            self.validation_queue.check_all()
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def check_for_next_block(self):
        tasks = asyncio.gather(
            self.validation_queue.check_for_next_block()
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

    def commit_consensus_block(self, hlc):
        tasks = asyncio.gather(
            self.validation_queue.commit_consensus_block(hlc)
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
        processing_results = get_processing_results(driver=self.driver, tx_message=tx_message, node_wallet=node_wallet)

        hlc_timestamp = tx_message['hlc_timestamp']

        self.validation_queue.append(
            processing_results=processing_results
        )

        result_hash = self.validation_queue.get_result_hash_for_vk(
            hlc_timestamp=hlc_timestamp,
            node_vk=node_wallet.verifying_key
        )

        tx_result_hash = tx_result_hash_from_tx_result_object(
            tx_result=processing_results['tx_result'],
            hlc_timestamp=hlc_timestamp,
            rewards=processing_results['rewards']
        )

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
            hlc_timestamp=processing_results_1['hlc_timestamp'],
            rewards=processing_results_1['rewards']
        )
        tx_result_hash_2 = tx_result_hash_from_tx_result_object(
            tx_result=processing_results_2['tx_result'],
            hlc_timestamp=processing_results_2['hlc_timestamp'],
            rewards=processing_results_1['rewards']
        )

        self.assertEqual(node_wallet_1_solution, tx_result_hash_1)
        self.assertEqual(node_wallet_2_solution, tx_result_hash_2)

        self.assertEqual(len(self.validation_queue), 1)
        self.assertEqual(self.validation_queue[0], hlc_timestamp)

    def test_append_hlc_timestamp_older_than_consensus_block_not_exist(self):
        receiver_wallet = Wallet()
        node_wallet = Wallet()

        transaction = get_new_currency_tx(wallet=self.wallet, amount="10.5", to=receiver_wallet.verifying_key)
        tx_message = get_tx_message(tx=transaction, node_wallet=node_wallet)
        processing_results = get_processing_results(driver=self.driver, tx_message=tx_message, node_wallet=node_wallet)

        hlc_timestamp = tx_message['hlc_timestamp']

        self.validation_queue.last_hlc_in_consensus = HLC_Clock().get_new_hlc_timestamp()
        self.validation_queue.append(processing_results=processing_results)
        result_hash = self.validation_queue.get_result_hash_for_vk(
            hlc_timestamp=hlc_timestamp,
            node_vk=node_wallet.verifying_key
        )

        #tx_result_hash = tx_result_hash_from_tx_result_object(tx_result=processing_results['tx_result'],
        #                                                      hlc_timestamp=hlc_timestamp)

        self.assertIsNone(result_hash)

        self.assertEqual(len(self.validation_queue), 0)
        #self.assertEqual(self.validation_queue[0], hlc_timestamp)

    def test_append_hlc_timestamp_older_than_consensus_block_exist(self):
        receiver_wallet = Wallet()
        node_wallet = Wallet()

        transaction = get_new_currency_tx(wallet=self.wallet, amount="10.5", to=receiver_wallet.verifying_key)
        tx_message = get_tx_message(tx=transaction, node_wallet=node_wallet)
        processing_results = get_processing_results(driver=self.driver, tx_message=tx_message, node_wallet=node_wallet)

        hlc_timestamp = tx_message['hlc_timestamp']

        self.validation_queue.last_hlc_in_consensus = HLC_Clock().get_new_hlc_timestamp()
        self.block = 'not none'

        self.validation_queue.append(processing_results=processing_results)
        result_hash = self.validation_queue.get_result_hash_for_vk(
            hlc_timestamp=hlc_timestamp,
            node_vk=node_wallet.verifying_key
        )

        self.assertIsNone(result_hash)
        self.assertEqual(len(self.validation_queue), 0)

    def test_append_validation_results_has_consensus(self):
        receiver_wallet = Wallet()
        node_wallet = Wallet()

        transaction = get_new_currency_tx(wallet=self.wallet, amount="10.5", to=receiver_wallet.verifying_key)
        tx_message = get_tx_message(tx=transaction, node_wallet=node_wallet)
        processing_results = get_processing_results(driver=self.driver, tx_message=tx_message, node_wallet=node_wallet)

        hlc_timestamp = tx_message['hlc_timestamp']

        self.validation_queue.validation_results[hlc_timestamp] = {}
        self.validation_queue.validation_results[hlc_timestamp]['last_check_info'] = {}
        self.validation_queue.validation_results[hlc_timestamp]['last_check_info']['has_consensus'] = True

        # TODO better assertion for this flow
        self.assertEqual(len(self.validation_queue), 1)
        self.validation_queue.append(processing_results=processing_results)
        self.assertEqual(len(self.validation_queue), 1)

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
        processing_results = get_processing_results(driver=self.driver, tx_message=tx_message, node_wallet=node_wallet)

        hlc_timestamp = tx_message['hlc_timestamp']
        self.validation_queue.append(processing_results=processing_results)

        self.assertTrue(self.validation_queue.awaiting_validation(hlc_timestamp=hlc_timestamp))

        self.assertIsNotNone(self.validation_queue.validation_results[hlc_timestamp]['solutions'][node_wallet.verifying_key])


    def test_get_results(self):
        node_wallet_1 = Wallet()
        node_wallet_2 = Wallet()

        processing_results_1, processing_results_2 = self.add_solutions(
            amount_of_solutions=2,
            node_wallets=[node_wallet_1, node_wallet_2]
        )

        hlc_timestamp = processing_results_1['hlc_timestamp']

        results = self.validation_queue.get_validation_result(hlc_timestamp=hlc_timestamp)

        self.assertIsNotNone(results)

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

        self.num_of_peers = 1

        # Await the queue attempting consensus
        self.process_next()

        self.assertFalse(self.hard_apply_block_called)
        self.assertEqual(self.validation_queue.last_hlc_in_consensus, "")

    def test_process_next__gets_block_from_network_if_consensus_stalled_and_there_is_later_consensus(self):
        self.add_solution()
        self.add_solutions(amount_of_solutions=2)

        self.num_of_peers = 1

        self.process_next()

        self.assertTrue(self.hard_apply_block_called)

    def test_process_next_hlc_has_consensus(self):
        pr = self.add_solution()
        self.validation_queue.validation_results[pr['hlc_timestamp']]['last_check_info']['has_consensus'] = True

        self.process_next()

        self.assertTrue(self.hard_apply_block_called)
        self.assertEqual(len(self.validation_queue), 0)

    def test_check_all_returns_if_already_checking(self):
        self.validation_queue.checking = True
        self.check_all()
        self.assertTrue(self.validation_queue.checking)

    def test_check_all_returns_if_no_results_not_in_consensus(self):
        self.check_all()
        self.assertFalse(self.validation_queue.checking)

    def test_check_all_reaches_consensus(self):
        pr = self.add_solution()

        self.assertFalse(self.validation_queue.validation_results[pr['hlc_timestamp']]['last_check_info']['has_consensus'])

        self.check_all()

        self.assertTrue(self.validation_queue.validation_results[pr['hlc_timestamp']]['last_check_info']['has_consensus'])

    def test_check_all_terminates_gracefully_on_empty_validation_results(self):
        pr = self.add_solution()

        self.validation_queue.validation_results[pr['hlc_timestamp']] = {}

        self.check_all()

        self.assertFalse(self.validation_queue.checking)

    def test_METHOD_add_consensus__adds_consensus_result(self):
        pr = self.add_solution()
        hlc = pr['hlc_timestamp']

        self.validation_queue.validation_results[hlc]['last_check_info'] = {
            'ideal_consensus_possible': False,
            'eager_consensus_possible': False,
            'has_consensus': True
        }

        consensus_result = {
            'ideal_consensus_possible': True,
            'eager_consensus_possible': True,
            'has_consensus': True
        }

        self.validation_queue.add_consensus_result(hlc, consensus_result)

        self.assertDictEqual(consensus_result, self.validation_queue.validation_results[hlc]['last_check_info'])


    def test_METHOD_add_consensus__changes_just_one_consensus_result(self):
        pr = self.add_solution()
        hlc = pr['hlc_timestamp']

        self.validation_queue.validation_results[hlc]['last_check_info'] = {
            'ideal_consensus_possible': False,
            'eager_consensus_possible': False,
            'has_consensus': False
        }

        consensus_result = {
            'ideal_consensus_possible': True,
            'has_consensus': False
        }

        self.validation_queue.add_consensus_result(hlc, consensus_result)

        self.assertTrue(self.validation_queue.validation_results[hlc]['last_check_info']['ideal_consensus_possible'])
        self.assertFalse(self.validation_queue.validation_results[hlc]['last_check_info']['eager_consensus_possible'])

    def test_METHOD_add_consensus__overwrites_dict_if_consensus_is_True(self):
        pr = self.add_solution()
        hlc = pr['hlc_timestamp']

        self.validation_queue.validation_results[hlc]['last_check_info'] = {
            'ideal_consensus_possible': True,
            'eager_consensus_possible': False,
            'has_consensus': False
        }

        consensus_result = {
            'ideal_consensus_possible': True,
            'eager_consensus_possible': False,
            'has_consensus': True,
            'new_value': 'something'
        }

        self.validation_queue.add_consensus_result(hlc, consensus_result)

        last_check_info = self.validation_queue.validation_results[hlc]['last_check_info']
        self.assertTrue(last_check_info['ideal_consensus_possible'])
        self.assertFalse(last_check_info['eager_consensus_possible'])
        self.assertDictEqual(consensus_result, last_check_info)

    def test_METHOD_add_consensus__returns_if_consensus_results_is_None(self):
        pr = self.add_solution()
        hlc = pr['hlc_timestamp']

        self.validation_queue.validation_results[hlc]['last_check_info'] = {
            'ideal_consensus_possible': False,
            'eager_consensus_possible': False,
            'has_consensus': 'something'
        }

        try:
            self.validation_queue.add_consensus_result(hlc, None)
        except Exception as err:
            self.fail("add_consensus should return on None and not raise any errors")


    def test_check_num_of_solutions_no_validation_results(self):
        self.assertEqual(0, self.validation_queue.check_num_of_solutions('sample_stamp'))

    def test_check_num_of_solutions_returns_correct_num_of_solutions(self):
        pr = self.add_solution()

        self.assertEqual(1, self.validation_queue.check_num_of_solutions(pr['hlc_timestamp']))

    def test_ideal_consensus_possible_returns_false_when_no_validation_results(self):
        self.assertFalse(self.validation_queue.check_ideal_consensus_possible('sample_stamp'))

    def test_ideal_consensus_possible_returns_true_when_indeed_possible(self):
        hlc = self.add_solution()['hlc_timestamp']

        self.assertTrue(self.validation_queue.check_ideal_consensus_possible(hlc))

    def test_ideal_consensus_possible_returns_false_not_valid_last_check_info(self):
        hlc = self.add_solution()['hlc_timestamp']

        self.validation_queue.validation_results[hlc]['last_check_info'] = None

        self.assertFalse(self.validation_queue.check_ideal_consensus_possible(hlc))

    def test_eager_consensus_possible_returns_false_when_no_validation_results(self):
        self.assertFalse(self.validation_queue.check_eager_consensus_possible('sample_stamp'))

    def test_eager_consensus_possible_returns_true_when_indeed_possible(self):
        hlc = self.add_solution()['hlc_timestamp']

        self.assertTrue(self.validation_queue.check_eager_consensus_possible(hlc))

    def test_eager_consensus_possible_returns_false_not_valid_last_check_info(self):
        hlc = self.add_solution()['hlc_timestamp']

        self.validation_queue.validation_results[hlc]['last_check_info'] = None

        self.assertFalse(self.validation_queue.check_eager_consensus_possible(hlc))

    def test_is_earliest_hlc_returns_false_no_validation_results(self):
        self.assertFalse(self.validation_queue.is_earliest_hlc('sample_stamp'))

    def test_is_earliest_hlc_returns_true_if_earliest(self):
        hlc = self.add_solution()['hlc_timestamp']

        self.assertTrue(self.validation_queue.is_earliest_hlc(hlc))

    def test_is_earliest_hlc_returns_false_if_not_earliest(self):
        self.add_solution()['hlc_timestamp']
        hlc = self.add_solution()

        self.assertFalse(self.validation_queue.is_earliest_hlc(hlc))

    def test_check_for_next_block_applies_block(self):
        hlc = self.add_solution()['hlc_timestamp']
        self.check_all()

        self.check_for_next_block()

        self.assertTrue(self.hard_apply_block_called)

    def test_check_for_next_block_handles_invalid_validation_result_entry_without_error(self):
        hlc = self.add_solution()['hlc_timestamp']
        self.validation_queue.validation_results[hlc]['last_check_info'] = {}
        self.check_all()

        self.check_for_next_block()

        self.assertFalse(self.hard_apply_block_called)

    def test_check_for_next_block_applies_only_latest_hlc(self):
        for i in range(2):
            self.add_solution()
        self.check_all()

        self.check_for_next_block()

        self.assertTrue(self.hard_apply_block_called)
        self.assertEqual(self.num_times_hard_apply_block_called, 1)

    def test_clear_solutions(self):
        self.validation_queue.validation_results = {
            'hlc_1': {
                'solutions': {
                    self.validation_queue.wallet.verifying_key: 'solution',
                    '2': 'solution'
                },
                'last_check_info': {},
                'proofs': {}
            },
            'hlc_2': {
                'solutions': {
                    self.validation_queue.wallet.verifying_key: 'solution'
                },
                'last_check_info': {},
                'proofs': {}
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
        self.validation_queue.clear_solutions(node_vk=self.validation_queue.wallet.verifying_key)

        self.assertIsNone(self.validation_queue.validation_results['hlc_1']['solutions'].get(self.validation_queue.wallet.verifying_key))
        self.assertIsNotNone(self.validation_queue.validation_results['hlc_1']['solutions'].get('2'))

        self.assertIsNone(self.validation_queue.validation_results['hlc_2']['solutions'].get(self.validation_queue.wallet.verifying_key))

        self.assertIsNone(self.validation_queue.validation_results['hlc_3']['solutions'].get(self.validation_queue.wallet.verifying_key))
        self.assertIsNotNone(self.validation_queue.validation_results['hlc_3']['solutions'].get('2'))

    def test_get_last_consensus_result_returns_empty_invalid_stamp(self):
        self.assertDictEqual({}, self.validation_queue.get_last_consensus_result('sample_stamp'))

    def test_get_last_consensus_result_returns_correct_results(self):
        hlc = self.add_solution()['hlc_timestamp']

        self.assertDictEqual(
            self.validation_queue.validation_results.get(hlc)['last_check_info'],
            self.validation_queue.get_last_consensus_result(hlc)
        )

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

    def test_get_proofs_from_results_returns_empty_list_if_no_consensus(self):
        hlc = self.add_solution()['hlc_timestamp']

        self.assertListEqual([], self.validation_queue.get_proofs_from_results(hlc))

    def test_get_recreated_tx_message_invalid_stamp_returns_none(self):
        self.assertIsNone(self.validation_queue.get_recreated_tx_message('sample_stamp'))

    def test_get_recreated_tx_message(self):
        pr = get_new_processing_result('result_hash', 'tx_results', self.wallet, 'sample_stamp')
        self.validation_queue.append(pr)
        
        self.assertDictEqual(
            {
                'tx': pr['tx_result'].get('transaction'),
                'hlc_timestamp': pr['hlc_timestamp'],
                'signature': pr['tx_message'].get('signature'),
                'sender': pr['tx_message'].get('signer')
            },
            self.validation_queue.get_recreated_tx_message(pr['hlc_timestamp'])
        )

    def test_consensus_matches_me_returns_true_if_matches(self):
        hlc = self.add_solution(node_wallet=self.wallet)['hlc_timestamp']
        self.check_all()

        self.assertTrue(self.validation_queue.consensus_matches_me(hlc))

    def test_consensus_matches_me_returns_false_if_doesnt_match(self):
        hlc = self.add_solution()['hlc_timestamp']
        self.check_all()

        self.assertFalse(self.validation_queue.consensus_matches_me(hlc))

    def test_commit_consensus_block(self):
        hlc = self.add_solution()['hlc_timestamp']

        self.commit_consensus_block(hlc)

        self.assertTrue(self.hard_apply_block_called)
        self.assertEqual(len(self.validation_queue.validation_results), 0)

    def test_commit_consensus_block_doesnt_update_last_hlc_in_consensus(self):
        hlc = self.add_solution()['hlc_timestamp']
        self.validation_queue.last_hlc_in_consensus = HLC_Clock().get_new_hlc_timestamp()

        self.commit_consensus_block(hlc)

        self.assertTrue(self.hard_apply_block_called)
        self.assertNotEqual(self.validation_queue.last_hlc_in_consensus, hlc)
        self.assertEqual(len(self.validation_queue.validation_results), 0)

    def test_hlc_has_solutions_returns_false_if_results_not_found_by_stamp(self):
        self.assertFalse(self.validation_queue.hlc_has_solutions('sample_stamp'))

    def test_hlc_has_solutions_returns_false_if_no_solutions(self):
        hlc = self.add_solution()['hlc_timestamp']
        del self.validation_queue.validation_results[hlc]['solutions']

        self.assertFalse(self.validation_queue.hlc_has_solutions(hlc))

    def test_hlc_has_solutions_returns_true_if_exist(self):
        hlc = self.add_solution()['hlc_timestamp']

        self.assertTrue(self.validation_queue.hlc_has_solutions(hlc))

    def test_count_solutions_returns_0_if_results_not_found_by_stamp(self):
        self.assertEqual(0, self.validation_queue.count_solutions('sample_stamp'))

    def test_count_solutions_returns_0_if_no_solutions(self):
        hlc = self.add_solution()['hlc_timestamp']
        del self.validation_queue.validation_results[hlc]['solutions']

        self.assertEqual(0, self.validation_queue.count_solutions(hlc))

    def test_count_solutions_returns_number_of_solutions(self):
        hlc = self.add_solution()['hlc_timestamp']

        self.assertEqual(1, self.validation_queue.count_solutions(hlc))

    def test_remove_all_hlcs_from_queue(self):
        hlc = HLC_Clock().get_new_hlc_timestamp()
        self.validation_queue.queue.append(hlc)

        self.validation_queue.remove_all_hlcs_from_queue(hlc)

        self.assertTrue(hlc not in self.validation_queue.queue)

    def test_prune_earlier_results_all_results_are_earlier(self):
        for i in range(2):
            self.add_solution()
        self.assertEqual(2, len(self.validation_queue.validation_results))

        self.validation_queue.prune_earlier_results(HLC_Clock().get_new_hlc_timestamp())

        self.assertEqual(0, len(self.validation_queue.validation_results))

    def test_prune_earlier_results_not_all_results_are_earlier(self):
        self.add_solution()
        earlier_than = HLC_Clock().get_new_hlc_timestamp()
        self.add_solution()

        self.assertEqual(2, len(self.validation_queue.validation_results))

        self.validation_queue.prune_earlier_results(earlier_than)

        self.assertEqual(1, len(self.validation_queue.validation_results))

    def test_clean_results_lookup_doesnt_clean_if_exists(self):
        hlc = self.add_solution(node_wallet=self.wallet)['hlc_timestamp']
        
        self.validation_queue.clean_results_lookup(hlc)

        self.assertEqual(1, len(self.validation_queue.validation_results[hlc]['result_lookup']))

    def test_clean_results_lookup_cleans_if_not_exists(self):
        hlc = self.add_solution()['hlc_timestamp']
        self.validation_queue.validation_results[hlc]['result_lookup']['sample_solution'] = 'sample_result'
        
        self.validation_queue.clean_results_lookup(hlc)

        self.assertIsNone(self.validation_queue.validation_results[hlc]['result_lookup'].get('sample_solution'))

    def test_get_key_list(self):
        expected = []
        for i in range(2):
            expected.append(self.add_solution()['hlc_timestamp'])

        self.assertListEqual(expected, self.validation_queue.get_key_list())

    def test_set_item(self):
        with self.assertRaises(ReferenceError) as cm:
            self.validation_queue['key'] = 'value'

    def test_len(self):
        self.assertEqual(0, len(self.validation_queue))

        hlc = self.add_solution()['hlc_timestamp']

        self.assertEqual(1, len(self.validation_queue))

        self.validation_queue.flush_hlc(hlc)

        self.assertEqual(0, len(self.validation_queue))

    def test_get_item_returns_none_on_invalid_index(self):
        self.assertIsNone(self.validation_queue[0])

    def test_get_item(self):
        first = self.add_solution()['hlc_timestamp']
        second = self.add_solution()['hlc_timestamp']
        
        self.assertEqual(self.validation_queue[0], first)
        self.assertEqual(self.validation_queue[1], second)

    def test_METHOD_check_one__checks_one_result_has_ideal(self):
        node_wallet_1 = Wallet()
        node_wallet_2 = Wallet()

        self.num_of_peers = 1

        processing_results_1, processing_results_2 = self.add_solutions(
            amount_of_solutions=2,
            node_wallets=[node_wallet_1, node_wallet_2]
        )

        hlc_timestamp = processing_results_1['hlc_timestamp']

        self.assertFalse(self.validation_queue.hlc_has_consensus(hlc_timestamp=hlc_timestamp))

        self.validation_queue.check_one(hlc_timestamp=hlc_timestamp)

        self.assertTrue(self.validation_queue.hlc_has_consensus(hlc_timestamp=hlc_timestamp))

    def test_METHOD_check_one__checks_one_result_has_failed(self):
        node_wallet_1 = Wallet()
        node_wallet_2 = Wallet()

        self.num_of_peers = 1

        processing_results_1, processing_results_2 = self.add_solutions(
            amount_of_solutions=2,
            node_wallets=[node_wallet_1, node_wallet_2]
        )

        hlc_timestamp = processing_results_1['hlc_timestamp']

        h = hashlib.sha3_256()
        encoded_tx = encode({'hlc_timestamp': hlc_timestamp}).encode()
        h.update(encoded_tx)
        solution_2 =  h.hexdigest()

        self.validation_queue.validation_results[hlc_timestamp]['solutions'][node_wallet_2.verifying_key] = solution_2

        solution_1 = self.validation_queue.validation_results[hlc_timestamp]['solutions'][node_wallet_1.verifying_key]

        if int(solution_1, 16) < int(solution_2, 16):
            expected_consensus_solution = solution_1
        else:
            expected_consensus_solution = solution_2

        self.assertFalse(self.validation_queue.hlc_has_consensus(hlc_timestamp=hlc_timestamp))

        self.check_all()

        self.assertTrue(self.validation_queue.hlc_has_consensus(hlc_timestamp=hlc_timestamp))

        self.assertEqual(expected_consensus_solution, self.validation_queue.validation_results[hlc_timestamp]['last_check_info']['solution'])

    def test_prints_debug_if_queue_is_empty(self):
        loop = asyncio.get_event_loop()
        self.async_sleep(2)
        loop.run_until_complete(self.validation_queue.process_next())

    def test_METHOD_process_all__escapes_if_check_time_greater_than_timeout(self):
        pr = self.add_solution()
        hlc = pr['hlc_timestamp']

        self.validation_queue.validation_results[hlc]['last_check_info'] = {
            'has_consensus': False
        }

        # Run the process_all routine, this should set the time it started checking
        self.process_next()

        # reduce timeout from 60 to 1 second for testing purposes
        self.validation_queue.checking_timeout = 1

        # sleep past timeout
        self.async_sleep(1.5)

        # The validation queue has a solution for this hlc and a time we started checking
        self.assertIsNotNone(self.validation_queue.validation_results.get(hlc))
        self.assertIsNotNone(self.validation_queue.started_checking.get(hlc))

        # Run the process_all routine, this should remove the hlc from the queue
        self.process_next()

        # The hlc was removed due to timeout
        self.assertIsNone(self.validation_queue.validation_results.get(hlc))
        self.assertIsNone(self.validation_queue.started_checking.get(hlc))

