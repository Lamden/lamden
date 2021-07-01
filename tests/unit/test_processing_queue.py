from unittest import TestCase

from contracting.db.driver import ContractDriver
from contracting.client import ContractingClient
from contracting.execution.executor import Executor

from lamden import storage
from lamden import rewards
from lamden.nodes import processing_queue
from lamden.crypto.wallet import Wallet
from lamden.nodes.hlc import HLC_Clock

import time
import hashlib
import random
import asyncio

tx1 = {
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
            'sender': 'd48b174f71efb9194e9cd2d58de078882bd172fcc7c8ac5ae537827542ae604e',
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

        self.processing_delay_secs = {
            'base': 0.75,
            'self': 0.75
        }

        self.running = True

        self.current_height = lambda: storage.get_latest_block_height(self.driver)
        self.current_hash = lambda: storage.get_latest_block_hash(self.driver)

        self.main_processing_queue = processing_queue.ProcessingQueue(
            driver=self.driver,
            client=self.client,
            wallet=self.wallet,
            hlc_clock=self.hlc_clock,
            processing_delay=self.processing_delay_secs,
            executor=self.executor,
            get_current_hash=self.current_hash,
            get_current_height=self.current_height,
            stop_node=self.stop,
            reward_manager=self.reward_manager
        )

        self.client.flush()

    def tearDown(self):
        self.main_processing_queue.stop()
        self.main_processing_queue.flush()

    async def await_queue_stopping(self):
        print (self.main_processing_queue.currently_processing)
        # Await the stopping of the queue
        await self.main_processing_queue.stopping()

    async def delay_processing(self, func, delay):
        print('\n')
        print('Starting Sleeping: ', time.time())
        await asyncio.sleep(delay)
        print('Done Sleeping: ', time.time())
        func()

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

    def stop(self):
        self.running = False

    def test_can_start(self):
        self.main_processing_queue.start()
        self.assertEqual(self.main_processing_queue.running, True)

    def test_can_start(self):
        self.main_processing_queue.start()
        self.assertEqual(self.main_processing_queue.running, True)

    def test_can_stop(self):
        self.main_processing_queue.stop()
        self.assertEqual(self.main_processing_queue.running, False)

    def test_can_await_stopping(self):
        # Mark the queue as currently processing
        self.main_processing_queue.start_processing()

        # Stop the queue
        self.main_processing_queue.stop()

        # Await the queue stopping and then mark the queue as not processing after X seconds
        tasks = asyncio.gather(
            self.delay_processing(func=self.main_processing_queue.stop_processing, delay=2)
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        # Assert the queue is stopped and not processing any transactions
        self.assertEqual(self.main_processing_queue.currently_processing, False)
        self.assertEqual(self.main_processing_queue.running, False)

    def test_append(self):
        # Add a bunch of transactions to the queue
        for i in range(10):
            self.main_processing_queue.append(tx=self.make_tx_message(tx1))

        # Assert all the transactions are in the queue
        self.assertEqual(len(self.main_processing_queue), 10)

    def test_process_next(self):
        async def process_next():
            # Call process next and get processing_results
            processing_results = await self.main_processing_queue.process_next()

            # assert the first HLC entered was the one that was processed
            self.assertEqual(processing_results['hlc_processed'], first_hlc)

        # load a bunch of transactions into the queue
        for i in range(10):
            self.main_processing_queue.append(tx=self.make_tx_message(tx1))
            self.assertEqual(len(self.main_processing_queue), i+1)

            # if this is the first transaction get the HLC for it for comparison later
            if i == 0:
                first_hlc = self.main_processing_queue.main_processing_queue[0]['hlc_timestamp']

        # Shuffle the processing queue so the hlcs are out of order
        random.shuffle(self.main_processing_queue.main_processing_queue)
        asyncio.ensure_future(process_next())