from lamden.crypto import transaction
from lamden.crypto.wallet import Wallet, verify
from lamden.crypto import canonical
from contracting.db.driver import decode, ContractDriver, InMemDriver
from contracting.client import ContractingClient
from lamden.nodes import execution, work
from lamden.nodes import masternode, delegate, base
from lamden import storage, authentication, router
import zmq.asyncio
import asyncio
import hashlib
from copy import deepcopy
from decimal import Decimal
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

    def test_execute_tx_returns_successful_output(self):
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

        e = execution.SerialExecutor(executor=self.client.executor)

        result = e.execute_tx(decode(tx), stamp_cost=20_000)

        self.assertEqual(result['status'], 0)
        self.assertEqual(result['state'][0]['key'], 'testing.v')
        self.assertEqual(result['state'][0]['value'],  'jeff')
        self.assertEqual(result['stamps_used'], 1)

    def test_stamp_deduction_on_fail(self):
        test_contract = '''
@export
def eat_stamps():
    while True:
        pass
        '''

        self.client.submit(test_contract, name='testing')

        self.client.raw_driver.commit()
        self.client.raw_driver.clear_pending_state()

        stu = Wallet()

        self.client.raw_driver.set(f'currency.balances:{stu.verifying_key}', 100000)

        tx = transaction.build_transaction(
            wallet=stu,
            contract='testing',
            function='eat_stamps',
            kwargs={},
            stamps=10000,
            processor='0' * 64,
            nonce=0
        )

        e = execution.SerialExecutor(executor=self.client.executor)

        self.client.executor.metering = True

        result = e.execute_tx(decode(tx), stamp_cost=200)

        self.assertEqual(result['status'], 1)
        self.assertEqual(result['state'][0]['key'], f'currency.balances:{stu.verifying_key}')
        self.assertEqual(result['state'][0]['value'], Decimal('99950.0'))
        self.assertEqual(result['stamps_used'], 10000)

    def test_generate_environment_creates_datetime_wrapped_object(self):
        timestamp = int(time.time())

        exe = execution.SerialExecutor(executor=self.client.executor)

        e = exe.generate_environment(self.client.raw_driver, timestamp, 'A' * 64)

        t = datetime.utcfromtimestamp(timestamp)

        #self.assertEqual(type(e['now']), Datetime)
        self.assertEqual(e['now'].year, t.year)
        self.assertEqual(e['now'].month, t.month)
        self.assertEqual(e['now'].day, t.day)
        self.assertEqual(e['now'].hour, t.hour)
        self.assertEqual(e['now'].minute, t.minute)
        self.assertEqual(e['now'].second, t.second)

    def test_generate_environment_creates_input_hash(self):
        timestamp = time.time()

        exe = execution.SerialExecutor(executor=self.client.executor)

        e = exe.generate_environment(self.client.raw_driver, timestamp, 'A' * 64)

        self.assertEqual(e['__input_hash'], 'A' * 64)

    def test_generate_environment_creates_block_hash(self):
        timestamp = time.time()

        exe = execution.SerialExecutor(executor=self.client.executor)

        e = exe.generate_environment(self.client.raw_driver, timestamp, 'A' * 64)

        self.assertEqual(e['block_hash'], storage.get_latest_block_hash(self.client.raw_driver))

    def test_generate_environment_creates_block_num(self):
        timestamp = time.time()

        exe = execution.SerialExecutor(executor=self.client.executor)

        e = exe.generate_environment(self.client.raw_driver, timestamp, 'A' * 64)

        self.assertEqual(e['block_num'], storage.get_latest_block_height(self.client.raw_driver) + 1)

    def test_execute_tx_batch_returns_all_transactions(self):
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

        e = execution.SerialExecutor(executor=self.client.executor)

        results = e.execute_tx_batch(
            driver=self.client.raw_driver,
            batch=tx_batch,
            timestamp=time.time(),
            input_hash='A' * 64,
            stamp_cost=20_000
        )

        td1, td2 = results

        self.assertEqual(td1['status'], 0)
        self.assertEqual(td1['state'][0]['key'], 'testing.v')
        self.assertEqual(td1['state'][0]['value'], 'howdy')
        self.assertEqual(td1['stamps_used'], 1)

        self.assertEqual(td2['status'], 0)
        self.assertEqual(len(td2['state']), 0)
        self.assertEqual(td2['stamps_used'], 1)

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

        e = execution.SerialExecutor(executor=self.client.executor)

        results = e.execute_tx_batch(
            driver=self.client.raw_driver,
            batch=tx_batch,
            timestamp=time.time(),
            input_hash='A' * 64,
            stamp_cost=20_000
        )

        td1, td2, td3, td4 = results

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

        exe = execution.SerialExecutor(executor=self.client.executor)

        results = exe.execute_work(
            driver=self.client.raw_driver,
            work=work,
            previous_block_hash='B' * 64,
            wallet=Wallet(),
            stamp_cost=20_000
        )

        sb1, sb2 = results

        td1, td2 = sb1['transactions']
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

        td1, td2 = sb2['transactions']
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

    def test_no_txs_merklizes_and_signs_input_hash(self):
        tx_batch_1 = {
            'transactions': [],
            'timestamp': time.time(),
            'input_hash': 'A' * 64
        }

        work = [tx_batch_1]

        w = Wallet()

        exe = execution.SerialExecutor(executor=self.client.executor)

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

    def test_acquire_work_1_master_gathers_tx_batches(self):
        ips = [
            'tcp://127.0.0.1:18001',
            'tcp://127.0.0.1:18002'
        ]

        dw = Wallet()
        mw = Wallet()

        self.authenticator.add_verifying_key(mw.verifying_key)
        self.authenticator.add_verifying_key(dw.verifying_key)
        self.authenticator.configure()

        mn = masternode.Masternode(
            socket_base=ips[0],
            ctx=self.ctx,
            wallet=mw,
            constitution={
                'masternodes': [mw.verifying_key],
                'delegates': [dw.verifying_key]
            },
            driver=ContractDriver(driver=InMemDriver())
        )

        dl = delegate.Delegate(
            socket_base=ips[1],
            ctx=self.ctx,
            wallet=dw,
            constitution={
                'masternodes': [mw.verifying_key],
                'delegates': [dw.verifying_key]
            },
            driver=ContractDriver(driver=InMemDriver())
        )

        peers = {
            mw.verifying_key: ips[0],
            dw.verifying_key: ips[1]
        }

        mn.network.peers = peers
        dl.network.peers = peers

        tasks = asyncio.gather(
            mn.router.serve(),
            dl.router.serve(),
            mn.send_work(),
            dl.acquire_work(),
            stop_server(mn.router, 1),
            stop_server(dl.router, 1),
        )

        _, _, _, w, _, _ = self.loop.run_until_complete(tasks)

        self.assertEqual(len(w), 1)
        self.assertEqual(w[0]['sender'], mw.verifying_key)

    def test_acquire_work_2_masters_gathers_tx_batches_pads_work_and_waits_if_missing(self):
        ips = [
            'tcp://127.0.0.1:18001',
            'tcp://127.0.0.1:18002'
        ]

        dw = Wallet()
        mw = Wallet()
        mw2 = Wallet()

        self.authenticator.add_verifying_key(mw.verifying_key)
        self.authenticator.add_verifying_key(dw.verifying_key)
        self.authenticator.configure()

        mn = masternode.Masternode(
            socket_base=ips[0],
            ctx=self.ctx,
            wallet=mw,
            constitution={
                'masternodes': [mw.verifying_key, mw2.verifying_key],
                'delegates': [dw.verifying_key]
            },
            driver=ContractDriver(driver=InMemDriver())
        )

        dl = delegate.Delegate(
            socket_base=ips[1],
            ctx=self.ctx,
            wallet=dw,
            constitution={
                'masternodes': [mw.verifying_key, mw2.verifying_key],
                'delegates': [dw.verifying_key]
            },
            driver=ContractDriver(driver=InMemDriver())
        )

        peers = {
            mw.verifying_key: ips[0],
            dw.verifying_key: ips[1],
            mw2.verifying_key: 'tpc://127.0.0.1:18003'
        }

        mn.network.peers = peers
        dl.network.peers = peers

        tasks = asyncio.gather(
            mn.router.serve(),
            dl.router.serve(),
            mn.send_work(),
            dl.acquire_work(),
            stop_server(mn.router, 1),
            stop_server(dl.router, 1),
        )

        _, _, _, w, _, _ = self.loop.run_until_complete(tasks)

        self.assertEqual(len(w), 2)
        self.assertEqual(w[0]['sender'], mw.verifying_key)

        self.assertEqual(w[1]['sender'], mw2.verifying_key)
        self.assertEqual(w[1]['input_hash'], mw2.verifying_key)
        self.assertEqual(w[1]['signature'], '0' * 128)

    def test_process_new_work_processes_tx_batch(self):
        ips = [
            'tcp://127.0.0.1:18001',
            'tcp://127.0.0.1:18002'
        ]

        dw = Wallet()
        mw = Wallet()

        self.authenticator.add_verifying_key(mw.verifying_key)
        self.authenticator.add_verifying_key(dw.verifying_key)
        self.authenticator.configure()

        mn = masternode.Masternode(
            socket_base=ips[0],
            ctx=self.ctx,
            wallet=mw,
            constitution={
                'masternodes': [mw.verifying_key],
                'delegates': [dw.verifying_key]
            },
            driver=ContractDriver(driver=InMemDriver())
        )

        mnq = router.QueueProcessor()
        mn.router.add_service(base.CONTENDER_SERVICE, mnq)

        dl = delegate.Delegate(
            socket_base=ips[1],
            ctx=self.ctx,
            wallet=dw,
            constitution={
                'masternodes': [mw.verifying_key],
                'delegates': [dw.verifying_key]
            },
            driver=ContractDriver(driver=InMemDriver())
        )

        peers = {
            mw.verifying_key: ips[0],
            dw.verifying_key: ips[1]
        }

        mn.network.peers = peers
        dl.network.peers = peers

        tasks = asyncio.gather(
            mn.router.serve(),
            dl.router.serve(),
            mn.send_work(),
            dl.process_new_work(),
            stop_server(mn.router, 1),
            stop_server(dl.router, 1),
        )

        self.loop.run_until_complete(tasks)

        sbc = mnq.q.pop(0)

        self.assertEqual(len(sbc), 1)
        self.assertEqual(sbc[0]['previous'], '0' * 64)
        self.assertEqual(sbc[0]['signer'], dw.verifying_key)

    def test_masternode_delegate_single_loop_works(self):
        ips = [
            'tcp://127.0.0.1:18001',
            'tcp://127.0.0.1:18002'
        ]

        dw = Wallet()
        mw = Wallet()

        self.authenticator.add_verifying_key(mw.verifying_key)
        self.authenticator.add_verifying_key(dw.verifying_key)
        self.authenticator.configure()

        mn = masternode.Masternode(
            socket_base=ips[0],
            ctx=self.ctx,
            wallet=mw,
            constitution={
                'masternodes': [mw.verifying_key],
                'delegates': [dw.verifying_key]
            },
            driver=ContractDriver(driver=InMemDriver())
        )

        dl = delegate.Delegate(
            socket_base=ips[1],
            ctx=self.ctx,
            wallet=dw,
            constitution={
                'masternodes': [mw.verifying_key],
                'delegates': [dw.verifying_key]
            },
            driver=ContractDriver(driver=InMemDriver())
        )

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

        # sbc = mnq.q.pop(0)
        #
        # self.assertEqual(len(sbc), 1)
        # self.assertEqual(sbc[0]['previous'], '0' * 64)
        # self.assertEqual(sbc[0]['signer'], dw.verifying_key)

    # def test_masternode_delegate_single_loop_commits_state_changes(self):
    #     ips = [
    #         'tcp://127.0.0.1:18001',
    #         'tcp://127.0.0.1:18002'
    #     ]
    #
    #     dw = Wallet()
    #     mw = Wallet()
    #
    #     self.authenticator.add_verifying_key(mw.verifying_key)
    #     self.authenticator.add_verifying_key(dw.verifying_key)
    #     self.authenticator.configure()
    #
    #     mnd = ContractDriver(driver=InMemDriver())
    #     mn = masternode.Masternode(
    #         socket_base=ips[0],
    #         ctx=self.ctx,
    #         wallet=mw,
    #         constitution={
    #             'masternodes': [mw.verifying_key],
    #             'delegates': [dw.verifying_key]
    #         },
    #         driver=mnd
    #     )
    #     sender = Wallet()
    #     mnd.set_var(contract='currency', variable='balances', arguments=[sender.verifying_key], value=1_000_000)
    #
    #     dld = ContractDriver(driver=InMemDriver())
    #     dld.set_var(contract='currency', variable='balances', arguments=[sender.verifying_key], value=1_000_000)
    #     dl = delegate.Delegate(
    #         socket_base=ips[1],
    #         ctx=self.ctx,
    #         wallet=dw,
    #         constitution={
    #             'masternodes': [mw.verifying_key],
    #             'delegates': [dw.verifying_key]
    #         },
    #         driver=dld
    #     )
    #
    #     tx = transaction.build_transaction(
    #         wallet=sender,
    #         contract='currency',
    #         function='transfer',
    #         kwargs={
    #             'amount': 1338,
    #             'to': 'jeff'
    #         },
    #         stamps=5000,
    #         nonce=0,
    #         processor=mw.verifying_key
    #     )
    #
    #     tx_decoded = decode(tx)
    #     mn.tx_batcher.queue.append(tx_decoded)
    #
    #     peers = {
    #         mw.verifying_key: ips[0],
    #         dw.verifying_key: ips[1]
    #     }
    #
    #     mn.network.peers = peers
    #     dl.network.peers = peers
    #
    #     tasks = asyncio.gather(
    #         mn.router.serve(),
    #         dl.router.serve(),
    #         mn.loop(),
    #         dl.loop(),
    #         stop_server(mn.router, 1),
    #         stop_server(dl.router, 1),
    #     )
    #
    #     self.loop.run_until_complete(tasks)
    #
    #     dbal = dld.get_var(contract='currency', variable='balances', arguments=['jeff'])
    #     mbal = mnd.get_var(contract='currency', variable='balances', arguments=['jeff'])
    #
    #     self.assertEqual(dbal, 1338)
    #     self.assertEqual(mbal, 1338)

    def test_masternode_delegate_single_loop_updates_block_num(self):
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

        dh = storage.get_latest_block_height(dld)
        mh = storage.get_latest_block_height(mnd)

        self.assertEqual(dh, 1)
        self.assertEqual(mh, 1)

class MockWork:
    def __init__(self, sender):
        self.sender = bytes.fromhex(sender)

    def __eq__(self, other):
        return self.sender == other.sender


class TestWork(TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_gather_work_waits_for_all(self):
        q = {}

        async def fill_q():
            q['1'] = 123
            await asyncio.sleep(0.1)
            q['3'] = 678
            await asyncio.sleep(0.5)
            q['x'] = 'zzz'

        tasks = asyncio.gather(
            fill_q(),
            work.gather_transaction_batches(q, expected_batches=3, timeout=5)
        )

        loop = asyncio.get_event_loop()
        _, w = loop.run_until_complete(tasks)

        expected = [123, 678, 'zzz']

        self.assertListEqual(expected, w)

    def test_gather_past_timeout_returns_current_work(self):
        q = {}

        async def fill_q():
            q['1'] = 123
            await asyncio.sleep(0.1)
            q['3'] = 678
            await asyncio.sleep(1.1)
            q['x'] = 'zzz'

        tasks = asyncio.gather(
            fill_q(),
            work.gather_transaction_batches(q, expected_batches=3, timeout=1)
        )

        loop = asyncio.get_event_loop()
        _, w = loop.run_until_complete(tasks)

        expected = [123, 678]

        self.assertListEqual(expected, w)

    def test_pad_work_does_nothing_if_complete(self):
        expected_masters = ['ab', 'cd', '23', '45']

        mw1 = {'sender': 'ab'}
        mw2 = {'sender': 'cd'}
        mw3 = {'sender': '23'}
        mw4 = {'sender': '45'}

        work_list = [mw1, mw2, mw3, mw4]
        w2 = deepcopy(work_list)

        work.pad_work(work_list, expected_masters=expected_masters)

        self.assertListEqual(work_list, w2)

    def test_pad_work_adds_tx_batches_if_missing_masters(self):
        expected_masters = ['ab', 'cd', '23', '45']

        mw1 = {'sender': 'ab'}
        mw2 = {'sender': 'cd'}

        work_list = [mw1, mw2]

        work.pad_work(work_list, expected_masters=expected_masters)

        a, b, c, d = work_list

        self.assertEqual(a, mw1)
        self.assertEqual(b, mw2)
        self.assertEqual(c['sender'], "23")
        self.assertEqual(c['input_hash'], "23")
        self.assertEqual(d['sender'], '45')
        self.assertEqual(d['input_hash'], "45")

    def test_filter_work_gets_rid_of_nones(self):
        w = {
            'timestamp': 0
        }

        filtered = work.filter_work([w, None])

        self.assertEqual(filtered, [w])

    def test_filter_sorts_by_time_stamp(self):
        w = {
            'timestamp': 125
        }

        w2 = {
            'timestamp': 123
        }

        w3 = {
            'timestamp': 1
        }

        filtered = work.filter_work([w, w2, w3])

        self.assertEqual(filtered, [w3, w2, w])
