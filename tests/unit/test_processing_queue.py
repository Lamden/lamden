from unittest import TestCase

from contracting.db.driver import ContractDriver, InMemDriver
from contracting.client import ContractingClient
from contracting.execution.executor import Executor
from contracting.stdlib.bridge.time import Datetime
from contracting.db.encoder import safe_repr

from lamden import storage
from lamden import rewards
from lamden.nodes import processing_queue
from lamden.crypto.wallet import Wallet
from lamden.nodes.hlc import HLC_Clock
from lamden.contracts import sync
from lamden.crypto.canonical import tx_hash_from_tx, format_dictionary, tx_result_hash_from_tx_result_object

import time
import math
import hashlib
import random
import asyncio
from datetime import datetime
from operator import itemgetter

def get_new_tx():
    return {
            'metadata': {
                'signature': '7eac4c17004dced6d079e260952fffa7750126d5d2c646ded886e6b1ab4f6da1e22f422aad2e1954c9529cfa71a043af8c8ef04ccfed6e34ad17c6199c0eba0e',
                'timestamp': time.time()
            },
            'payload': {
                'contract': 'currency',
                'function': 'transfer',
                'kwargs': {
                    'amount': {'__fixed__': '5'},
                    'to': '6e4f96fa89c508d2842bef3f7919814cd1f64c16954d653fada04e61cc997206'
                },
                'nonce': 0,
                'processor': '92e45fb91c8f76fbfdc1ff2a58c2e901f3f56ec38d2f10f94ac52fcfa56fce2e',
                'sender': "d48b174f71efb9194e9cd2d58de078882bd172fcc7c8ac5ae537827542ae604e",
                'stamps_supplied': 5000
            }
        }


class TestProcessingQueue(TestCase):
    def setUp(self):
        self.driver = ContractDriver(driver=InMemDriver())
        self.client = ContractingClient(
            driver=self.driver,
            submission_filename='./helpers/submission.py'
        )
        self.wallet = Wallet()

        self.hlc_clock = HLC_Clock()
        self.last_processed_hlc = self.hlc_clock.get_new_hlc_timestamp()
        self.last_hlc_in_consensus = '0'

        self.processing_delay_secs = {
            'base': 0.1,
            'self': 0.1
        }

        self.running = True
        self.reprocess_was_called = False
        self.catchup_was_called = False

        self.current_height = lambda: storage.get_latest_block_height(self.driver)
        self.current_hash = lambda: storage.get_latest_block_hash(self.driver)

        self.main_processing_queue = processing_queue.TxProcessingQueue(
            driver=self.driver,
            client=self.client,
            wallet=self.wallet,
            hlc_clock=self.hlc_clock,
            processing_delay=lambda: self.processing_delay_secs,
            stop_node=self.stop,
            reprocess=self.reprocess_called,
            get_last_hlc_in_consensus=self.get_last_hlc_in_consensus,
            check_if_already_has_consensus=self.check_if_already_has_consensus,
            pause_all_queues=self.pause_all_queues,
            unpause_all_queues=self.unpause_all_queues,
        )

        self.client.flush()
        self.sync()

    def tearDown(self):
        self.main_processing_queue.stop()
        self.main_processing_queue.flush()

    async def pause_all_queues(self):
        return

    def unpause_all_queues(self):
        return

    async def reprocess_called(self, tx):
        print("ROLLBACK CALLED")
        self.reprocess_was_called = True

    def catchup_called(self):
        print("CATCHUP CALLED")
        self.catchup_was_called = True

    def get_last_hlc_in_consensus(self):
        return self.last_hlc_in_consensus

    def check_if_already_has_consensus(self, hlc_timestamp):
        return None, None

    def sync(self):
        sync.setup_genesis_contracts(['stu', 'raghu', 'steve'], client=self.client)

    def make_tx_message(self, tx, hlc=None):
        hlc_timestamp = hlc or self.hlc_clock.get_new_hlc_timestamp()
        tx_hash = tx_hash_from_tx(tx=tx)

        signature = self.wallet.sign(f'{tx_hash}{hlc_timestamp}')

        return {
            'tx': tx,
            'hlc_timestamp': hlc_timestamp,
            'signature': signature,
            'sender': self.wallet.verifying_key
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

        # Assert message received timestamps are set
        for tx in self.main_processing_queue.queue:
            self.assertIsNotNone(tx['hlc_timestamp'])

    def test_append_tx_with_stamp_earlier_than_last_in_consensus(self):
        tx = self.make_tx_message(get_new_tx())
        self.last_hlc_in_consensus = self.hlc_clock.get_new_hlc_timestamp()
        self.main_processing_queue.append(tx)

        self.assertEqual(0, len(self.main_processing_queue))

    def test_flush(self):
        # Add a bunch of transactions to the queue
        for i in range(10):
            self.main_processing_queue.append(tx=self.make_tx_message(get_new_tx()))

        # flush queue
        self.main_processing_queue.flush()

        # Assert queue is empty
        self.assertEqual(len(self.main_processing_queue), 0)

    def test_sort_queue(self):
        for i in range(10):
            self.main_processing_queue.append(tx=self.make_tx_message(get_new_tx()))
        sorted_q = self.main_processing_queue.queue.copy()
        random.shuffle(self.main_processing_queue.queue)
        self.main_processing_queue.sort_queue()
        self.assertListEqual(sorted_q, self.main_processing_queue.queue)

    def test_hlc_earlier_than_consensus(self):
        hlc = self.hlc_clock.get_new_hlc_timestamp()
        self.last_hlc_in_consensus = self.hlc_clock.get_new_hlc_timestamp()
        self.assertTrue(self.main_processing_queue.hlc_earlier_than_consensus(hlc))

    def test_process_next(self):
        # load a bunch of transactions into the queue
        for i in range(10):
            self.main_processing_queue.append(tx=self.make_tx_message(get_new_tx()))
            self.assertEqual(i+1, len(self.main_processing_queue))

            # if this is the first transaction get the HLC for it for comparison later
            if i == 0:
                first_tx = self.main_processing_queue.queue[0]

        hold_time = self.processing_delay_secs['base'] + self.processing_delay_secs['self'] + 0.1

        # Await the queue stopping and then mark the queue as not processing after X seconds
        tasks = asyncio.gather(
            self.delay_processing_await(self.main_processing_queue.process_next, hold_time),
        )
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(tasks)
        processing_results = res[0]

        print(processing_results.get('hlc_timestamp'))

        hlc_timestamp = processing_results.get('hlc_timestamp')

        # assert the first HLC entered was the one that was processed
        self.assertEqual(hlc_timestamp, first_tx.get('hlc_timestamp'))
        self.assertIsNotNone(processing_results.get('proof'))
        self.assertIsNotNone(processing_results.get('tx_result'))
        self.assertEqual(self.main_processing_queue.currently_processing_hlc, '')

    def test_hlc_already_in_queue(self):
        tx_info = self.make_tx_message(get_new_tx())
        tx_info['hlc_timestamp'] = self.hlc_clock.get_new_hlc_timestamp()

        self.main_processing_queue.append(tx=tx_info)

        self.assertTrue(self.main_processing_queue.hlc_already_in_queue(tx_info['hlc_timestamp']))
        self.assertFalse(self.main_processing_queue.hlc_already_in_queue(self.hlc_clock.get_new_hlc_timestamp()))

    def test_process_next_return_value(self):
        self.main_processing_queue.append(tx=self.make_tx_message(get_new_tx()))

        hold_time = self.processing_delay_secs['base'] + self.processing_delay_secs['self'] + 0.1

        time.sleep(hold_time)

        loop = asyncio.get_event_loop()
        hlc_timestamp = loop.run_until_complete(self.main_processing_queue.process_next())

        self.assertIsNotNone(hlc_timestamp)


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
        hlc_timestamp = loop.run_until_complete(tasks)[0]

        self.assertIsNotNone(hlc_timestamp)

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

    def test_process_next_tx_with_hlc_less_than_last_in_consensus(self):
        tx = self.make_tx_message(get_new_tx())
        tx['hlc_timestamp'] = '1'
        self.main_processing_queue.append(tx=tx)
        self.last_hlc_in_consensus = '2'

        hold_time = self.processing_delay_secs['base'] + self.processing_delay_secs['self'] + 0.1

        # Await the queue stopping and then mark the queue as not processing after X seconds
        tasks = asyncio.gather(
            self.delay_processing_await(self.main_processing_queue.process_next, hold_time),
        )
        loop = asyncio.get_event_loop()
        processing_results = loop.run_until_complete(tasks)[0]

        self.assertIsNone(processing_results)
        self.assertEqual(self.main_processing_queue.currently_processing_hlc, '')

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

    def test_process_next_rollback_on_earlier_hlc(self):
        tx_info = self.make_tx_message(get_new_tx())
        tx_info['hlc_timestamp'] = self.hlc_clock.get_new_hlc_timestamp()

        self.main_processing_queue.last_processed_hlc = self.hlc_clock.get_new_hlc_timestamp()

        self.main_processing_queue.append(tx=tx_info)

        hold_time = self.processing_delay_secs['base'] + self.processing_delay_secs['self'] + 0.1

        # Await the queue stopping and then mark the queue as not processing after X seconds
        tasks = asyncio.gather(
            self.delay_processing_await(self.main_processing_queue.process_next, hold_time),
        )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tasks)

        self.assertTrue(self.reprocess_was_called)
        self.assertFalse(self.main_processing_queue.currently_processing)

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

    def test_process_tx(self):
        sbc = self.main_processing_queue.process_tx(tx=self.make_tx_message(get_new_tx()))

        self.assertIsNotNone(sbc)

    def test_get_environment(self):
        tx = self.make_tx_message(get_new_tx())
        environment = self.main_processing_queue.get_environment(tx=tx)

        nanos = self.main_processing_queue.hlc_clock.get_nanos(timestamp=tx['hlc_timestamp'])

        h = hashlib.sha3_256()
        h.update('{}'.format(nanos).encode())
        nanos_hash = h.hexdigest()

        h = hashlib.sha3_256()
        h.update('{}'.format(tx['hlc_timestamp']).encode())
        hlc_hash = h.hexdigest()

        now = Datetime._from_datetime(
                datetime.utcfromtimestamp(math.ceil(nanos / 1e9))
            )

        self.assertEqual(environment['block_hash'], nanos_hash)
        self.assertEqual(environment['block_num'], nanos)
        self.assertEqual(environment['__input_hash'], hlc_hash)
        self.assertEqual(environment['now'], now)
        self.assertEqual(environment['AUXILIARY_SALT'], tx['signature'])

    def test_execute_tx(self):
        tx = self.make_tx_message(get_new_tx())
        environment = self.main_processing_queue.get_environment(tx=tx)

        result = self.main_processing_queue.execute_tx(
            transaction=tx['tx'],
            stamp_cost=self.client.get_var(contract='stamp_cost', variable='S', arguments=['value']),
            environment=environment
        )

        self.assertIsNotNone(result)

    def test_process_tx_output(self):
        tx = self.make_tx_message(get_new_tx())
        environment = self.main_processing_queue.get_environment(tx=tx)
        stamp_cost = self.client.get_var(contract='stamp_cost', variable='S', arguments=['value'])
        output = self.main_processing_queue.execute_tx(
            transaction=tx['tx'],
            stamp_cost=stamp_cost,
            environment=environment
        )

        tx_result = self.main_processing_queue.process_tx_output(
            output=output,
            transaction=tx['tx'],
            stamp_cost=stamp_cost
        )

        self.assertIsNotNone(tx_result)

    def test_determine_writes_from_output(self):
        tx = self.make_tx_message(get_new_tx())
        environment = self.main_processing_queue.get_environment(tx=tx)
        stamp_cost = self.client.get_var(contract='stamp_cost', variable='S', arguments=['value'])
        transaction = tx['tx']
        output = self.main_processing_queue.execute_tx(
            transaction=transaction,
            stamp_cost=stamp_cost,
            environment=environment
        )

        for code in [0, 1]:
            writes = self.main_processing_queue.determine_writes_from_output(
                status_code=code,
                ouput_writes=output['writes'],
                stamps_used=output['stamps_used'],
                stamp_cost=stamp_cost,
                tx_sender=transaction['payload']['sender']
            )
            if code == 0:
                self.assertListEqual(writes, [{'key': k, 'value': v} for k, v in output['writes'].items()])
            else:
                sender_balance = self.driver.get_var(
                    contract='currency',
                    variable='balances',
                    arguments=[transaction['payload']['sender']],
                    mark=False
                )
                # Calculate only stamp deductions
                stamps_used = output.get('stamps_used')
                to_deduct = stamps_used / stamp_cost
                new_bal = 0
                try:
                    new_bal = sender_balance - to_deduct
                except TypeError:
                    pass
                self.assertListEqual(writes, [{'key': 'currency.balances:{}'.format(transaction['payload']['sender']),'value': new_bal}])

    def test_sign_tx_results(self):
        timestamp = self.hlc_clock.get_new_hlc_timestamp()
        result = 'sample result',
        rewards = [{}, {}]

        self.assertDictEqual(
            self.main_processing_queue.sign_tx_results(result, timestamp, rewards),
            {
                'signature': self.main_processing_queue.wallet.sign(tx_result_hash_from_tx_result_object(
                    tx_result=result,
                    hlc_timestamp=timestamp,
                    rewards=rewards
                )),
                'signer': self.main_processing_queue.wallet.verifying_key
            }
        )

    def test_get_hlc_hash_from_tx(self):
        tx = self.make_tx_message(get_new_tx())
        h = hashlib.sha3_256()
        h.update('{}'.format(tx['hlc_timestamp']).encode())

        self.assertEqual(self.main_processing_queue.get_hlc_hash_from_tx(tx), h.hexdigest())

    def test_get_nanos_from_tx(self):
        tx = self.make_tx_message(get_new_tx())

        self.assertEqual(self.main_processing_queue.hlc_clock.get_nanos(timestamp=tx['hlc_timestamp']), self.main_processing_queue.get_nanos_from_tx(tx))

    def test_get_now_from_nanos(self):
        tx = self.make_tx_message(get_new_tx())
        nanos = self.main_processing_queue.get_nanos_from_tx(tx)

        self.assertEqual(self.main_processing_queue.get_now_from_nanos(nanos), Datetime._from_datetime(datetime.utcfromtimestamp(math.ceil(nanos / 1e9))))

    def test_METHOD_filter_queue(self):
        tx_1 = self.make_tx_message(tx=get_new_tx(), hlc="1")
        tx_3 = self.make_tx_message(tx=get_new_tx(), hlc="3")

        self.main_processing_queue.append(tx_1)
        self.main_processing_queue.append(tx_3)

        self.assertTrue(self.main_processing_queue.hlc_already_in_queue(hlc_timestamp='1'))
        self.assertTrue(self.main_processing_queue.hlc_already_in_queue(hlc_timestamp='3'))

        self.last_hlc_in_consensus = '2'

        self.main_processing_queue.filter_queue()

        self.assertFalse(self.main_processing_queue.hlc_already_in_queue(hlc_timestamp='1'))
        self.assertTrue(self.main_processing_queue.hlc_already_in_queue(hlc_timestamp='3'))

    def test_processing_transactions_does_not_drop_state(self):
        num_of_transactions = 1000

        processing_delay_secs = {
            'base': 0,
            'self': 0
        }

        self.main_processing_queue.processing_delay = lambda: processing_delay_secs
        #self.main_processing_queue.executor.metering = True

        self.driver.driver.set('currency.balances:d48b174f71efb9194e9cd2d58de078882bd172fcc7c8ac5ae537827542ae604e', 10000000)

        loop = asyncio.get_event_loop()
        for i in range(num_of_transactions):
            tx = self.make_tx_message(tx=get_new_tx())
            self.main_processing_queue.append(tx=tx)
            processing_results = loop.run_until_complete(self.main_processing_queue.process_next())
            tx_result = processing_results.get('tx_result')
            self.assertGreater(len(tx_result['state']), 0)
            self.driver.soft_apply(tx.get('hlc_timestamp'))