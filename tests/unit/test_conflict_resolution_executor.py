from lamden.crypto import transaction
from lamden.crypto.wallet import Wallet, verify
from lamden.crypto import canonical
from lamden.crypto.canonical import tx_hash_from_tx
from contracting.db.driver import decode, ContractDriver, InMemDriver
from contracting.client import ContractingClient
from contracting.execution.executor import Executor

from lamden.nodes.delegate import execution, work
from lamden.nodes import masternode, delegate, base
from lamden import storage, authentication, router
import zmq.asyncio
import asyncio
import hashlib
from copy import deepcopy
from collections import OrderedDict

import time
from datetime import datetime

from unittest import TestCase


def generate_blocks(number_of_blocks, subblocks=[]):
    previous_hash = '0' * 64
    previous_number = 0

    blocks = []
    for i in range(number_of_blocks):
        if len(subblocks) > i:
            subblock = subblocks[i]
        else:
            subblock = []

        new_block = canonical.block_from_subblocks(
            subblocks=subblock,
            previous_hash=previous_hash,
            block_num=previous_number + 1
        )

        blocks.append(new_block)

        previous_hash = new_block['hash']
        previous_number += 1

    return blocks


async def stop_server(s, timeout):
    await asyncio.sleep(timeout)
    s.stop()


class TestDelegate(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.loop = asyncio.new_event_loop()
        self.driver = ContractDriver(driver=InMemDriver())
        self.client = ContractingClient(driver=self.driver)
        self.client.flush()
        execution.PoolExecutor = self.client.executor
        asyncio.set_event_loop(self.loop)

        self.authenticator = authentication.SocketAuthenticator(
            client=self.client, ctx=self.ctx
        )

    def tearDown(self):
        self.client.flush()
        self.driver.flush()
        self.authenticator.authenticator.stop()
        self.ctx.destroy()
        self.loop.close()

    def calc_rerun(self, e, tx_batch):
        results = e.execute_tx_batch(
            driver=self.client.raw_driver,
            batch=tx_batch,
            timestamp=time.time(),
            input_hash='A' * 64,
            stamp_cost=20_000
        )
        rez_batch = [results]
        tx_bad, tx_bad_idx = e.check_conflict2(rez_batch)
        if len(tx_bad) > 0:
            rez_batch2 = e.rerun_txs(
                driver=self.client.raw_driver,
                batch=tx_bad,
                timestamp=time.time(),
                input_hash='A' * 64,
                stamp_cost=20_000,
                tx_idx=tx_bad_idx,
                result0=rez_batch,
            )
            results = rez_batch2[0]
        return results

    def tx_sort_by_hash(self, tx_batch, results):
        tx_dict = {}
        for i in range( len(tx_batch['transactions'])):
            tx_hash = tx_hash_from_tx( tx_batch['transactions'][i])
            for r in results:
                if tx_hash == r['hash']:
                    tx_dict[i] = r

        tx_dict_ordered = OrderedDict(sorted(tx_dict.items()))
        new_d = [v for _,v in tx_dict_ordered.items()]
        return new_d


    def test1_execute_tx_returns_successful_output(self):
        test_contract = '''
v = Variable()

@construct
def seed():
    v.set('hello')

@export
def set(var: str):
    v.set(var)

@export
def get():
    return v.get()
                '''

        self.client.submit(test_contract, name='testing')

        self.client.raw_driver.commit()
        self.client.raw_driver.clear_pending_state()

        stu = Wallet()

        tx = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='set',
            kwargs={'var': 'jeff'},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )

        e = execution.ConflictResolutionExecutor()

        result = e.execute_tx(decode(tx), stamp_cost=20_000)
        e.stop_pool()

        self.assertEqual(result['status'], 0)
        self.assertEqual(result['state'][0]['key'], 'testing.v')
        self.assertEqual(result['state'][0]['value'],  'jeff')
        self.assertEqual(result['stamps_used'], 1)

    def test2_single_tx_batch_with_failed_transactions(self):
        test_contract = '''
v = Variable()

@construct
def seed():
    v.set('hello')

@export
def set(var: str):
    v.set(var)

@export
def get():
    return v.get()
        '''

        self.client.submit(test_contract, name='testing')

        self.client.raw_driver.commit()
        self.client.raw_driver.clear_pending_state()

        stu = Wallet()

        tx = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='set',
            kwargs={'var': 'howdy'},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )

        tx = decode(tx)

        tx2 = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='non_exist_get',
            kwargs={},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )

        tx2 = decode(tx2)

        tx_batch = {
            'transactions': [tx, tx2]
        }

        e = execution.ConflictResolutionExecutor()
        results = self.calc_rerun(e, tx_batch)
        td1, td2 = self.tx_sort_by_hash(tx_batch, results)

        self.assertEqual(td1['status'], 0)
        self.assertEqual(td1['state'][0]['key'], 'testing.v')
        self.assertEqual(td1['state'][0]['value'], 'howdy')
        self.assertEqual(td1['stamps_used'], 1)

        self.assertEqual(td2['status'], 1)
        self.assertEqual(len(td2['state']), 0)
        self.assertEqual(td2['stamps_used'], 1)
        self.assertEqual(td2['result'][0:len('AttributeError')], 'AttributeError')
        e.stop_pool()

    def test3_two_tx_batches_no_conflict(self):
        """3. Two tx batches that do not conflict works as expected"""
        test_contract = '''
v = Variable()
v2 = Variable()

@construct
def seed():
    v.set('hello')
    v2.set('hello2')

@export
def set(var: str):
    v.set(var)

@export
def get():
    return v.get()

@export
def set2(var: str):
    v2.set(var)

@export
def get2():
    return v2.get()

        '''

        self.client.submit(test_contract, name='testing')

        self.client.raw_driver.commit()
        self.client.raw_driver.clear_pending_state()

        stu = Wallet()

        tx1_1 = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='set',
            kwargs={'var': '123'},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )
        tx1_1 = decode(tx1_1)

        tx_batch_1 = {
            'transactions': [tx1_1],
            'timestamp': time.time(),
            'input_hash': 'A' * 64
        }


        jeff = Wallet()
        tx2_1 = transaction.build_transaction(
            wallet=jeff,
            contract='testing',
            function='set2',
            kwargs={'var': '222'},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )
        tx2_1 = decode(tx2_1)

        tx_batch_2 = {
            'transactions': [tx2_1],
            'timestamp': time.time(),
            'input_hash': 'A' * 64
        }

        work = [tx_batch_1, tx_batch_2]

        exe = execution.ConflictResolutionExecutor()
        results = exe.execute_work(
            driver=self.client.raw_driver,
            work=work,
            previous_block_hash='B' * 64,
            wallet=Wallet(),
            stamp_cost=20_000
        )

        sb1, sb2 = results
        td1 = sb1['transactions'][0]
        self.assertEqual(td1['status'], 0)
        self.assertEqual(td1['state'][0]['key'], 'testing.v')
        self.assertEqual(td1['state'][0]['value'], '123')

        td1 = sb2['transactions'][0]

        self.assertEqual(td1['status'], 0)
        self.assertEqual(td1['state'][0]['key'], 'testing.v2')
        self.assertEqual(td1['state'][0]['value'], '222')
        self.assertEqual(td1['stamps_used'], 1)

        self.assertEqual(sb2['input_hash'], tx_batch_2['input_hash'])
        self.assertEqual(sb2['subblock'], 1)
        self.assertEqual(sb2['previous'], 'B' * 64)
        exe.stop_pool()

    def test4_two_tx_batch_conflict(self):
        test_contract = '''
v = Variable()

@construct
def seed():
    v.set('hello')

@export
def set(var: str):
    v.set(var)

@export
def get():
    return v.get()
        '''

        self.client.submit(test_contract, name='testing')

        self.client.raw_driver.commit()
        self.client.raw_driver.clear_pending_state()

        stu = Wallet()

        tx = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='set',
            kwargs={'var': 'howdy'},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )

        tx = decode(tx)

        tx2 = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='get',
            kwargs={},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )

        tx2 = decode(tx2)

        tx_batch = {
            'transactions': [tx, tx2]
        }

        e = execution.ConflictResolutionExecutor()
        results = self.calc_rerun(e, tx_batch)
        td1, td2 = self.tx_sort_by_hash(tx_batch, results)

        self.assertEqual(td1['status'], 0)
        self.assertEqual(td1['state'][0]['key'], 'testing.v')
        self.assertEqual(td1['state'][0]['value'], 'howdy')
        self.assertEqual(td1['stamps_used'], 1)

        self.assertEqual(td2['status'], 0)
        self.assertEqual(len(td2['state']), 0)
        self.assertEqual(td2['stamps_used'], 1)
        e.stop_pool()

    def test_execute_tx_batch_returns_all_transactions_4_in_order(self):
        test_contract = '''
v = Variable()

@construct
def seed():
    v.set('hello')

@export
def set(var: str):
    v.set(var)

@export
def get():
    return v.get()
        '''

        self.client.submit(test_contract, name='testing')

        self.client.raw_driver.commit()
        self.client.raw_driver.clear_pending_state()

        stu = Wallet()

        tx = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='set',
            kwargs={'var': 'howdy'},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )

        tx = decode(tx)

        tx2 = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='get',
            kwargs={},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )

        tx2 = decode(tx2)

        tx3 = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='set',
            kwargs={'var': 'something'},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )

        tx3 = decode(tx3)

        tx4 = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='set',
            kwargs={'var': 'something2'},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )

        tx4 = decode(tx4)

        tx_batch = {
            'transactions': [tx, tx2, tx3, tx4]
        }

        e = execution.ConflictResolutionExecutor()
        results = self.calc_rerun(e, tx_batch)

        td1, td2, td3, td4 = self.tx_sort_by_hash(tx_batch, results)

        self.assertEqual(td1['status'], 0)
        self.assertEqual(td1['state'][0]['key'], 'testing.v')
        self.assertEqual(td1['state'][0]['value'], 'howdy')
        self.assertEqual(td1['stamps_used'], 1)

        self.assertEqual(td2['status'], 0)
        self.assertEqual(len(td2['state']), 0)
        self.assertEqual(td2['stamps_used'], 1)

        self.assertEqual(td3['status'], 0)
        self.assertEqual(td3['state'][0]['key'], 'testing.v')
        self.assertEqual(td3['state'][0]['value'], 'something')
        self.assertEqual(td3['stamps_used'], 1)

        self.assertEqual(td4['status'], 0)
        self.assertEqual(td4['state'][0]['key'], 'testing.v')
        self.assertEqual(td4['state'][0]['value'], 'something2')
        self.assertEqual(td4['stamps_used'], 1)
        e.stop_pool()

    def test_execute_work_multiple_transaction_batches_works(self):
        test_contract = '''
v = Variable()

@construct
def seed():
    v.set('hello')

@export
def set(var: str):
    v.set(var)

@export
def get():
    return v.get()
        '''

        self.client.submit(test_contract, name='testing')

        self.client.raw_driver.commit()
        self.client.raw_driver.clear_pending_state()

        stu = Wallet()

        tx1_1 = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='set',
            kwargs={'var': 'howdy'},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )

        tx1_1 = decode(tx1_1)

        tx1_2 = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='get',
            kwargs={},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )

        tx1_2 = decode(tx1_2)

        tx_batch_1 = {
            'transactions': [tx1_1, tx1_2],
            'timestamp': time.time(),
            'input_hash': 'C' * 64
        }

        tx2_1 = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='set',
            kwargs={'var': '123'},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )

        tx2_1 = decode(tx2_1)

        jeff = Wallet()
        tx2_2 = transaction.build_transaction(
            wallet=jeff,
            contract='testing',
            function='set',
            kwargs={'var': 'poo'},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )

        tx2_2 = decode(tx2_2)

        tx_batch_2 = {
            'transactions': [tx2_1, tx2_2],
            'timestamp': time.time(),
            'input_hash': 'A' * 64
        }

        work = [tx_batch_1, tx_batch_2]

        exe = execution.ConflictResolutionExecutor()
        results = exe.execute_work(
            driver=self.client.raw_driver,
            work=work,
            previous_block_hash='B' * 64,
            wallet=Wallet(),
            stamp_cost=20_000
        )

        sb1, sb2 = results
        td1, td2  = self.tx_sort_by_hash(work[0], sb1['transactions'])

        self.assertEqual(td1['status'], 0)
        self.assertEqual(td1['state'][0]['key'], 'testing.v')
        self.assertEqual(td1['state'][0]['value'], 'howdy')
        self.assertEqual(td1['stamps_used'], 1)

        self.assertEqual(td2['status'], 0)
        self.assertEqual(len(td2['state']), 0)
        self.assertEqual(td2['stamps_used'], 1)

        self.assertEqual(sb1['input_hash'], tx_batch_1['input_hash'])
        self.assertEqual(sb1['subblock'], 0)
        self.assertEqual(sb1['previous'], 'B' * 64)

        td1, td2  = self.tx_sort_by_hash(work[1], sb2['transactions'])

        self.assertEqual(td1['status'], 0)
        self.assertEqual(td1['state'][0]['key'], 'testing.v')
        self.assertEqual(td1['state'][0]['value'], '123')
        self.assertEqual(td1['stamps_used'], 1)

        self.assertEqual(td2['status'], 0)
        self.assertEqual(td2['state'][0]['key'], 'testing.v')
        self.assertEqual(td2['state'][0]['value'], 'poo')
        self.assertEqual(td2['stamps_used'], 1)

        self.assertEqual(sb2['input_hash'], tx_batch_2['input_hash'])
        self.assertEqual(sb2['subblock'], 1)
        self.assertEqual(sb2['previous'], 'B' * 64)
        exe.stop_pool()

    def test_no_txs_merklizes_and_signs_input_hash(self):
        tx_batch_1 = {
            'transactions': [],
            'timestamp': time.time(),
            'input_hash': 'A' * 64
        }

        work = [tx_batch_1]

        w = Wallet()

        exe = execution.ConflictResolutionExecutor()

        results = exe.execute_work(
            driver=self.client.raw_driver,
            work=work,
            previous_block_hash='B' * 64,
            wallet=w,
            stamp_cost=20_000
        )

        self.assertTrue(verify(w.verifying_key, results[0]['input_hash'], results[0]['merkle_tree']['signature']))

        h = hashlib.sha3_256()
        h.update(bytes.fromhex(results[0]['input_hash']))

        self.assertEqual(h.hexdigest(), results[0]['merkle_tree']['leaves'][0])
        exe.stop_pool()

    def test5_execute_work_multiple_transaction_batches_works(self):
        """5. Two tx batches where one reads a value and the other one writes to the same value conflict and are rerun"""
        test_contract = '''
v = Variable()

@construct
def seed():
    v.set('hello')

@export
def set(var: str):
    v.set(var)

@export
def get():
    return v.get()
        '''

        self.client.submit(test_contract, name='testing')

        self.client.raw_driver.commit()
        self.client.raw_driver.clear_pending_state()

        stu = Wallet()

        tx1_2 = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='get',
            kwargs={},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )

        tx1_2 = decode(tx1_2)

        tx_batch_1 = {
            'transactions': [tx1_2],
            'timestamp': time.time(),
            'input_hash': 'C' * 64
        }

        tx2_1 = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='set',
            kwargs={'var': '123'},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )

        tx2_1 = decode(tx2_1)

        jeff = Wallet()
        tx2_2 = transaction.build_transaction(
            wallet=jeff,
            contract='testing',
            function='get',
            kwargs={},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )

        tx2_2 = decode(tx2_2)

        tx_batch_2 = {
            'transactions': [tx2_1, tx2_2],
            'timestamp': time.time(),
            'input_hash': 'A' * 64
        }

        work = [tx_batch_1, tx_batch_2]

        exe = execution.ConflictResolutionExecutor()
        results = exe.execute_work(
            driver=self.client.raw_driver,
            work=work,
            previous_block_hash='B' * 64,
            wallet=Wallet(),
            stamp_cost=20_000
        )

        sb1, sb2 = results
        td1 = sb1['transactions'][0]
        self.assertEqual(td1['status'], 0)
        # self.assertEqual(td1['result'], '123')

        td1, td2 = self.tx_sort_by_hash(work[1], sb2['transactions'])

        self.assertEqual(td1['status'], 0)
        self.assertEqual(td1['state'][0]['key'], 'testing.v')
        self.assertEqual(td1['state'][0]['value'], '123')
        self.assertEqual(td1['stamps_used'], 1)

        self.assertEqual(td2['status'], 0)
        # self.assertEqual(td2['state'][0]['key'], 'testing.v')
        # self.assertEqual(td2['state'][0]['value'], '123')
        self.assertEqual(td2['stamps_used'], 1)

        self.assertEqual(sb2['input_hash'], tx_batch_2['input_hash'])
        self.assertEqual(sb2['subblock'], 1)
        self.assertEqual(sb2['previous'], 'B' * 64)
        exe.stop_pool()

    def test6_execute_work_multiple_transaction_batches_works(self):
        """6. Same as #5 but switch the batches the transactions appear"""
        test_contract = '''
v = Variable()

@construct
def seed():
    v.set('hello')

@export
def set(var: str):
    v.set(var)

@export
def get():
    return v.get()
        '''

        self.client.submit(test_contract, name='testing')

        self.client.raw_driver.commit()
        self.client.raw_driver.clear_pending_state()

        stu = Wallet()

        tx1_2 = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='get',
            kwargs={},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )

        tx1_2 = decode(tx1_2)

        tx_batch_2 = {
            'transactions': [tx1_2],
            'timestamp': time.time(),
            'input_hash': 'C' * 64
        }

        tx2_1 = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='set',
            kwargs={'var': '123'},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )

        tx2_1 = decode(tx2_1)

        jeff = Wallet()
        tx2_2 = transaction.build_transaction(
            wallet=jeff,
            contract='testing',
            function='get',
            kwargs={},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )

        tx2_2 = decode(tx2_2)

        tx_batch_1 = {
            'transactions': [tx2_1, tx2_2],
            'timestamp': time.time(),
            'input_hash': 'A' * 64
        }

        work = [tx_batch_1, tx_batch_2]

        exe = execution.ConflictResolutionExecutor()
        results = exe.execute_work(
            driver=self.client.raw_driver,
            work=work,
            previous_block_hash='B' * 64,
            wallet=Wallet(),
            stamp_cost=20_000
        )

        sb1, sb2 = results
        td1 = sb2['transactions'][0]
        self.assertEqual(td1['status'], 0)
        # self.assertEqual(td1['result'], '123')

        td1, td2 = self.tx_sort_by_hash(work[0], sb1['transactions'])

        self.assertEqual(td1['status'], 0)
        self.assertEqual(td1['state'][0]['key'], 'testing.v')
        self.assertEqual(td1['state'][0]['value'], '123')
        self.assertEqual(td1['stamps_used'], 1)

        self.assertEqual(td2['status'], 0)
        # self.assertEqual(td2['state'][0]['key'], 'testing.v')
        # self.assertEqual(td2['state'][0]['value'], '123')
        self.assertEqual(td2['stamps_used'], 1)

        self.assertEqual(sb2['input_hash'], tx_batch_2['input_hash'])
        self.assertEqual(sb2['subblock'], 1)
        self.assertEqual(sb2['previous'], 'B' * 64)
        exe.stop_pool()

    def test7_execute_work_multiple_transaction_batches_works(self):
        """7. Two tx batches that read the same value do not conflict and are processed as expected"""
        test_contract = '''
v = Variable()

@construct
def seed():
    v.set('hello')

@export
def set(var: str):
    v.set(var)

@export
def get():
    return v.get()
        '''

        self.client.submit(test_contract, name='testing')

        self.client.raw_driver.commit()
        self.client.raw_driver.clear_pending_state()

        stu = Wallet()

        tx1_2 = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='get',
            kwargs={},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )

        tx1_2 = decode(tx1_2)

        tx_batch_2 = {
            'transactions': [tx1_2],
            'timestamp': time.time(),
            'input_hash': 'C' * 64
        }

        jeff = Wallet()
        tx2_2 = transaction.build_transaction(
            wallet=jeff,
            contract='testing',
            function='get',
            kwargs={},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )

        tx2_2 = decode(tx2_2)

        tx_batch_1 = {
            'transactions': [tx2_2],
            'timestamp': time.time(),
            'input_hash': 'A' * 64
        }

        work = [tx_batch_1, tx_batch_2]

        exe = execution.ConflictResolutionExecutor()
        results = exe.execute_work(
            driver=self.client.raw_driver,
            work=work,
            previous_block_hash='B' * 64,
            wallet=Wallet(),
            stamp_cost=20_000
        )

        sb1, sb2 = results
        td1 = sb1['transactions'][0]
        self.assertEqual(td1['status'], 0)

        td2 = sb2['transactions'][0]

        self.assertEqual(td2['status'], 0)
        self.assertEqual(td2['stamps_used'], 1)

        self.assertEqual(sb2['input_hash'], tx_batch_2['input_hash'])
        self.assertEqual(sb2['subblock'], 1)
        self.assertEqual(sb2['previous'], 'B' * 64)
        exe.stop_pool()

    def test8_execute_work_multiple_transaction_batches_works(self):
        """8. Four tx batches that have multiple transactions in them, but not the same number in each,
        have multiple conflicts with each other.
        a. One transaction should conflict with two transactions that do not conflict with one another
        b. A conflicts with B and C, but B does not conflict with C.
        The reruns should be processed according to the conflict square in this document
        """
        test_contract = '''
v1 = Variable()
v2 = Variable()
v3 = Variable()
v4 = Variable()
v5 = Variable()

@construct
def seed():
    v1.set('hello1')
    v2.set('hello2')
    v3.set('hello3')
    v4.set('hello4')
    v5.set('hello5')

@export
def set1(var: str):
    v1.set(var)

@export
def get1():
    return v1.get()

@export
def set2(var: str):
    v2.set(var)

@export
def get2():
    return v2.get()

@export
def set3(var: str):
    v1.set(var)
    v2.set(var)
    v3.set(var)

@export
def get3():
    return v3.get()

@export
def set4(var: str):
    v4.set(var)

@export
def get4():
    return v4.get()

@export
def set5(var: str):
    v5.set(var)

@export
def get5():
    return v5.get()

        '''

        self.client.submit(test_contract, name='testing')

        self.client.raw_driver.commit()
        self.client.raw_driver.clear_pending_state()

        stu = Wallet()
        tx1_1 = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='set1',
            kwargs={'var': '111'},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )
        tx1_1 = decode(tx1_1)

        tx1_2 = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='set2',
            kwargs={'var': '222'},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )
        tx1_2 = decode(tx1_2)

        tx1_3 = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='set3',
            kwargs={'var': '333'},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )
        tx1_3 = decode(tx1_3)


        tx_batch_1 = {
            'transactions': [tx1_1, tx1_2, tx1_3],
            'timestamp': time.time(),
            'input_hash': 'C' * 64
        }

        jeff = Wallet()
        tx2_1 = transaction.build_transaction(
            wallet=jeff,
            contract='testing',
            function='get1',
            kwargs={},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )
        tx2_1 = decode(tx2_1)

        tx2_2 = transaction.build_transaction(
            wallet=jeff,
            contract='testing',
            function='get2',
            kwargs={},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )
        tx2_2 = decode(tx2_2)

        tx2_3 = transaction.build_transaction(
            wallet=jeff,
            contract='testing',
            function='get3',
            kwargs={},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )
        tx2_3 = decode(tx2_3)

        tx_batch_2 = {
            'transactions': [tx2_1, tx2_2, tx2_3],
            'timestamp': time.time(),
            'input_hash': 'A' * 64
        }

        stu2 = Wallet()
        tx3_1 = transaction.build_transaction(
            wallet=stu2,
            contract='testing',
            function='set4',
            kwargs={'var': '444'},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )
        tx3_1 = decode(tx3_1)

        tx3_2 = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='get4',
            kwargs={},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )
        tx3_2 = decode(tx3_2)

        tx_batch_3 = {
            'transactions': [tx3_1, tx3_2],
            'timestamp': time.time(),
            'input_hash': 'A' * 64
        }

        stu3 = Wallet()
        tx4_1 = transaction.build_transaction(
            wallet=stu3,
            contract='testing',
            function='set5',
            kwargs={'var': '555'},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )
        tx4_1 = decode(tx4_1)

        tx4_2 = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='get5',
            kwargs={},
            stamps=100_000,
            processor='0' * 64,
            nonce=0
        )
        tx4_2 = decode(tx4_2)

        tx_batch_4 = {
            'transactions': [tx4_1, tx4_2],
            'timestamp': time.time(),
            'input_hash': 'A' * 64
        }


        work = [tx_batch_1, tx_batch_2, tx_batch_3, tx_batch_4]

        exe = execution.ConflictResolutionExecutor()
        results = exe.execute_work(
            driver=self.client.raw_driver,
            work=work,
            previous_block_hash='B' * 64,
            wallet=Wallet(),
            stamp_cost=20_000
        )

        sb1, sb2, sb3, sb4 = results
        # td1 = sb1['transactions'][0]
        td1, td2, td3 = self.tx_sort_by_hash(work[0], sb1['transactions'])
        print('td1=', td1)
        print('td2=', td2)
        print('td3=', td3)

        self.assertEqual(td1['status'], 0)
        td2 = sb2['transactions'][0]

        self.assertEqual(td2['status'], 0)
        self.assertEqual(td2['stamps_used'], 1)

        self.assertEqual(sb2['input_hash'], tx_batch_2['input_hash'])
        self.assertEqual(sb2['subblock'], 1)
        self.assertEqual(sb2['previous'], 'B' * 64)
        exe.stop_pool()

    def test_masternode_delegate_single_loop_commits_state_changes(self):
        ips = [
            'tcp://127.0.0.1:18001',
            'tcp://127.0.0.1:18002'
        ]

        dw = Wallet()
        mw = Wallet()

        self.authenticator.add_verifying_key(mw.verifying_key)
        self.authenticator.add_verifying_key(dw.verifying_key)
        self.authenticator.configure()

        mnd = ContractDriver(driver=InMemDriver())
        mn = masternode.Masternode(
            socket_base=ips[0],
            ctx=self.ctx,
            wallet=mw,
            constitution={
                'masternodes': [mw.verifying_key],
                'delegates': [dw.verifying_key]
            },
            driver=mnd
        )
        sender = Wallet()
        mnd.set_var(contract='currency', variable='balances', arguments=[sender.verifying_key], value=1_000_000)

        dld = ContractDriver(driver=InMemDriver())
        dld.set_var(contract='currency', variable='balances', arguments=[sender.verifying_key], value=1_000_000)
        dl = delegate.Delegate(
            socket_base=ips[1],
            ctx=self.ctx,
            wallet=dw,
            constitution={
                'masternodes': [mw.verifying_key],
                'delegates': [dw.verifying_key]
            },
            driver=dld
        )

        tx = transaction.build_transaction(
            wallet=sender,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 1338,
                'to': 'jeff'
            },
            stamps=5000,
            nonce=0,
            processor=mw.verifying_key
        )

        tx_decoded = decode(tx)
        mn.tx_batcher.queue.append(tx_decoded)

        peers = {
            mw.verifying_key: ips[0],
            dw.verifying_key: ips[1]
        }

        mn.network.peers = peers
        dl.network.peers = peers

        tasks = asyncio.gather(
            mn.router.serve(),
            dl.router.serve(),
            mn.loop(),
            dl.loop(),
            stop_server(mn.router, 1),
            stop_server(dl.router, 1),
        )

        self.loop.run_until_complete(tasks)

        dbal = dld.get_var(contract='currency', variable='balances', arguments=['jeff'])
        mbal = mnd.get_var(contract='currency', variable='balances', arguments=['jeff'])

        self.assertEqual(dbal, 1338)
        self.assertEqual(mbal, 1338)

