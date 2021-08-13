from unittest import TestCase

from contracting.db.driver import ContractDriver
from contracting.client import ContractingClient
from contracting.execution.executor import Executor

from lamden import storage
from lamden import rewards
from lamden.nodes import processing_queue
from lamden.crypto.wallet import Wallet
from lamden.nodes.hlc import HLC_Clock
from lamden.contracts import sync

import time
import hashlib
import random
import asyncio
from datetime import datetime
from operator import itemgetter


def get_new_tx():
    return {
            'metadata': {
                'signature': '7eac4c17004dced6d079e260952fffa7750126d5d2c646ded886e6b1ab4f6da1e22f422aad2e1954c9529cfa71a043af8c8ef04ccfed6e34ad17c6199c0eba0e',
                'timestamp': 1624049397
            },
            'payload': {
                'contract': 'currency',
                'function': 'transfer',
                'kwargs': {
                    'amount': {'__fixed__': '499950'},
                    'to': '6e4f96fa89c508d2842bef3f7919814cd1f64c16954d653fada04e61cc997206',
                    'nonce': 0,
                    'processor': '92e45fb91c8f76fbfdc1ff2a58c2e901f3f56ec38d2f10f94ac52fcfa56fce2e'
                },
                'sender': "d48b174f71efb9194e9cd2d58de078882bd172fcc7c8ac5ae537827542ae604e",
                'stamps_supplied': 100
            }
        }


class TestProcessingQueue(TestCase):
    def setUp(self):
        self.driver = ContractDriver()
        self.client = ContractingClient(
            driver=self.driver
        )
        self.wallet = Wallet()

        self.executor = Executor(driver=self.driver)
        self.reward_manager = rewards.RewardManager()

        self.hlc_clock = HLC_Clock()
        self.last_processed_hlc = self.hlc_clock.get_new_hlc_timestamp()
        self.last_hlc_in_consensus = '0'

        self.processing_delay_secs = {
            'base': 0.1,
            'self': 0.1
        }

        self.running = True
        self.rollback_was_called = False
        self.catchup_was_called = False

        self.current_height = lambda: storage.get_latest_block_height(self.driver)
        self.current_hash = lambda: storage.get_latest_block_hash(self.driver)

        self.main_processing_queue = processing_queue.TxProcessingQueue(
            driver=self.driver,
            client=self.client,
            wallet=self.wallet,
            hlc_clock=self.hlc_clock,
            processing_delay=lambda: self.processing_delay_secs,
            executor=self.executor,
            get_current_hash=self.current_hash,
            get_current_height=self.current_height,
            stop_node=self.stop,
            reward_manager=self.reward_manager,
            rollback=self.rollback_called,
            get_last_processed_hlc=self.get_last_processed_hlc,
            get_last_hlc_in_consensus=self.get_last_hlc_in_consensus,
            check_if_already_has_consensus=self.check_if_already_has_consensus
        )

        self.client.flush()
        self.sync()

    def tearDown(self):
        self.main_processing_queue.stop()
        self.main_processing_queue.flush()

    async def rollback_called(self):
        print("ROLLBACK CALLED")
        self.rollback_was_called = True

    def catchup_called(self):
        print("CATCHUP CALLED")
        self.catchup_was_called = True

    def get_last_processed_hlc(self):
        return self.last_processed_hlc

    def get_last_hlc_in_consensus(self):
        return self.last_hlc_in_consensus

    def check_if_already_has_consensus(self, hlc_timestamp):
        return None, None

    def sync(self):
        sync.setup_genesis_contracts(['stu', 'raghu', 'steve'], ['tejas', 'alex2'], client=self.client)

    def make_tx_message(self, tx):
        timestamp = int(time.time())

        h = hashlib.sha3_256()
        h.update('{}'.format(timestamp).encode())
        input_hash = h.hexdigest()

        signature = self.wallet.sign(input_hash)

        return {
            'tx': tx,
            'timestamp': timestamp,
            'hlc_timestamp': self.hlc_clock.get_new_hlc_timestamp(),
            'signature': signature,
            'sender': self.wallet.verifying_key,
            'input_hash': input_hash
        }

    async def delay_processing_await(self, func, delay):
        print('\n')
        print('Starting Sleeping: ', time.time())
        await asyncio.sleep(delay)
        print('Done Sleeping: ', time.time())
        if func:
            return await func()

    def stop(self):
        self.running = False

    def test_append(self):
        # Add a bunch of transactions to the queue
        for i in range(10):
            self.main_processing_queue.append(tx=self.make_tx_message(get_new_tx()))

        # Assert all the transactions are in the queue
        self.assertEqual(len(self.main_processing_queue), 10)

    def test_flush(self):
        # Add a bunch of transactions to the queue
        for i in range(10):
            self.main_processing_queue.append(tx=self.make_tx_message(get_new_tx()))

        # Add a received timestamp
        self.main_processing_queue.message_received_timestamps['testing_hlc'] = 0

        # flush queue
        self.main_processing_queue.flush()

        # Assert queue is empty
        self.assertEqual(len(self.main_processing_queue), 0)
        self.assertEqual(len(self.main_processing_queue.message_received_timestamps), 0)

    def test_hold_1_time_self(self):
        hold_time = self.main_processing_queue.hold_time(tx=self.make_tx_message(get_new_tx()))
        print({'hold_time': hold_time})
        self.assertEqual(self.processing_delay_secs['self'] + self.processing_delay_secs['base'], hold_time)

    def test_hold_2_time_base(self):
        new_tx_message = self.make_tx_message(get_new_tx())
        new_wallet = Wallet()
        new_tx_message['sender'] = new_wallet.verifying_key

        hold_time = self.main_processing_queue.hold_time(tx=new_tx_message)
        print({'hold_time': hold_time})
        self.assertEqual(self.processing_delay_secs['base'], hold_time)

    def test_process_next(self):
        # load a bunch of transactions into the queue
        for i in range(10):
            self.main_processing_queue.append(tx=self.make_tx_message(get_new_tx()))
            self.assertEqual(len(self.main_processing_queue), i+1)

            # if this is the first transaction get the HLC for it for comparison later
            if i == 0:
                first_tx = self.main_processing_queue.queue[0]

        # Shuffle the processing queue so the hlcs are out of order
        random.shuffle(self.main_processing_queue.queue)

        hold_time = self.processing_delay_secs['base'] + self.processing_delay_secs['self'] + 0.1

        # Await the queue stopping and then mark the queue as not processing after X seconds
        tasks = asyncio.gather(
            self.delay_processing_await(self.main_processing_queue.process_next, hold_time),
        )
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        # assert the first HLC entered was the one that was processed
        self.assertEqual(res[0]['hlc_timestamp'], first_tx['hlc_timestamp'])

    def test_process_next_return_value(self):
        self.main_processing_queue.append(tx=self.make_tx_message(get_new_tx()))

        hold_time = self.processing_delay_secs['base'] + self.processing_delay_secs['self'] + 0.1

        # Await the queue stopping and then mark the queue as not processing after X seconds
        tasks = asyncio.gather(
            self.delay_processing_await(self.main_processing_queue.process_next, hold_time),
        )
        loop = asyncio.get_event_loop()
        processing_results = loop.run_until_complete(tasks)[0]

        hlc_timestamp, result, transaction_processed = itemgetter(
            'hlc_timestamp', 'result', 'transaction_processed'
        )(processing_results)

        self.assertIsNotNone(hlc_timestamp)
        self.assertIsNotNone(result)
        self.assertIsNotNone(transaction_processed)

    def test_process_next_return_value_tx_already_in_consensus_in_sync(self):
        def mock_check_if_already_has_consensus(hlc_timestamp):
            return {
                'hlc_timestamp': hlc_timestamp,
                'result': True,
                'transaction_processed': True
            }, False

        self.main_processing_queue.check_if_already_has_consensus = mock_check_if_already_has_consensus
        self.main_processing_queue.append(tx=self.make_tx_message(get_new_tx()))

        hold_time = self.processing_delay_secs['base'] + self.processing_delay_secs['self'] + 0.1

        # Await the queue stopping and then mark the queue as not processing after X seconds
        tasks = asyncio.gather(
            self.delay_processing_await(self.main_processing_queue.process_next, hold_time),
        )
        loop = asyncio.get_event_loop()
        processing_results = loop.run_until_complete(tasks)[0]

        hlc_timestamp, result, transaction_processed = itemgetter(
            'hlc_timestamp', 'result', 'transaction_processed'
        )(processing_results)

        self.assertIsNotNone(hlc_timestamp)
        self.assertIsNotNone(result)
        self.assertIsNotNone(transaction_processed)

    def test_process_next_returns_none_if_len_0(self):
        self.main_processing_queue.flush()

        hold_time = self.processing_delay_secs['base'] + self.processing_delay_secs['self'] + 0.1

        # Await the queue stopping and then mark the queue as not processing after X seconds
        tasks = asyncio.gather(
            self.delay_processing_await(self.main_processing_queue.process_next, hold_time),
        )
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        # assert the first HLC entered was the one that was processed
        self.assertIsNone(res[0])

    def test_process_next_returns_none_hlc_already_in_consensus(self):
        self.last_hlc_in_consensus = '2'

        tx= self.make_tx_message(get_new_tx())
        tx['hlc_timestamp'] = '1'

        self.main_processing_queue.append(tx=tx)

        hold_time = self.processing_delay_secs['base'] + self.processing_delay_secs['self'] + 0.1

        # Await the queue stopping and then mark the queue as not processing after X seconds
        tasks = asyncio.gather(
            self.delay_processing_await(self.main_processing_queue.process_next, hold_time),
        )
        loop = asyncio.get_event_loop()
        processing_results = loop.run_until_complete(tasks)[0]

        self.assertIsNone(processing_results)

    def test_process_next_returns_none_if_less_than_delay(self):
        # load a transactions into the queue
        self.main_processing_queue.append(tx=self.make_tx_message(get_new_tx()))

        # Await the queue stopping and then mark the queue as not processing without waiting a delay
        tasks = asyncio.gather(
            self.delay_processing_await(self.main_processing_queue.process_next, 0),
        )
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)

        # assert the first HLC entered was the one that was processed
        self.assertIsNone(res[0])

        # Tx is still in queue to be processed
        self.assertEqual(len(self.main_processing_queue), 1)

    def test_process_tx(self):
        sbc = self.main_processing_queue.process_tx(tx=self.make_tx_message(get_new_tx()))

        self.assertIsNotNone(sbc)

    def test_execute_tx(self):
        tx = self.make_tx_message(get_new_tx())
        environment = self.main_processing_queue.get_environment(tx=tx)

        result = self.main_processing_queue.execute_tx(
            transaction=tx['tx'],
            stamp_cost=self.client.get_var(contract='stamp_cost', variable='S', arguments=['value']),
            hlc_timestamp=tx['hlc_timestamp'],
            environment=environment
        )

        self.assertIsNotNone(result)

    def test_get_environment(self):
        tx = self.make_tx_message(get_new_tx())
        environment = self.main_processing_queue.get_environment(tx=tx)

        self.assertEqual(environment['block_hash'], '0' * 64)
        self.assertEqual(environment['block_num'], 0)
        self.assertEqual(environment['__input_hash'], tx['input_hash'])
        self.assertEqual(environment['now'], self.main_processing_queue.get_now_from_tx(tx=tx))
        self.assertEqual(environment['AUXILIARY_SALT'], tx['tx']['metadata']['signature'])

    def test_rollback_on_process_earlier_hlc(self):
        self.last_processed_hlc = '2'

        tx_info = self.make_tx_message(get_new_tx())
        tx_info['hlc_timestamp'] = '1'

        self.main_processing_queue.append(tx=tx_info)

        hold_time = self.processing_delay_secs['base'] + self.processing_delay_secs['self'] + 0.1

        # Await the queue stopping and then mark the queue as not processing after X seconds
        tasks = asyncio.gather(
            self.delay_processing_await(self.main_processing_queue.process_next, hold_time),
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        self.assertTrue(self.rollback_was_called)

    def test_hlc_already_in_queue(self):
        tx_info = self.make_tx_message(get_new_tx())
        tx_info['hlc_timestamp'] = '1'

        self.main_processing_queue.append(tx=tx_info)

        self.assertTrue(self.main_processing_queue.hlc_already_in_queue('1'))
        self.assertFalse(self.main_processing_queue.hlc_already_in_queue('2'))
