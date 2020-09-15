from unittest import TestCase

import lamden.nodes.masternode.masternode
from lamden.nodes.delegate.delegate import Delegate
from lamden.storage import StateDriver
from lamden.nodes.delegate import execution
from contracting.client import ContractingClient
from contracting.stdlib.bridge.time import Datetime
from lamden.crypto.wallet import Wallet
from lamden.crypto.transaction import TransactionBuilder
from lamden.crypto import canonical
from contracting import config
import time
from lamden.crypto.transaction_batch import transaction_list_to_transaction_batch
import zmq.asyncio
import datetime
from tests.random_txs import random_block
import os
import capnp
import asyncio
from lamden.messages import capnp_struct as schemas

block_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/blockdata.capnp')

def make_ipc(p):
    try:
        os.mkdir(p)
    except:
        pass
class MockDriver:
    def __init__(self):
        self.latest_block_hash = b'\x00' * 32
        self.latest_block_num = 999

def put_test_contract(client):
    test_contract = '''
v = Variable()

@construct
def seed():
    v.set('hello')

@export
def set(var):
    v.set(var)

@export
def get():
    return v.get()
        '''

    client.submit(test_contract, name='testing')

def get_tx_batch():
    w = Wallet()
    tx = TransactionBuilder(
        sender='stu',
        contract='testing',
        function='set',
        kwargs={'var': 'howdy'},
        stamps=100_000,
        processor=b'\x00' * 32,
        nonce=0
    )
    tx.sign(w.signing_key)
    tx.serialize()

    currency_contract = 'currency'
    balances_hash = 'balances'

    balances_key = '{}{}{}{}{}'.format(currency_contract,
                                       config.INDEX_SEPARATOR,
                                       balances_hash,
                                       config.DELIMITER,
                                       w.verifying_key)

    driver = StateDriver()
    driver.set(balances_key, 1_000_000)
    driver.commit()

    w = Wallet()
    tx2 = TransactionBuilder(
        sender='stu',
        contract='testing',
        function='get',
        kwargs={},
        stamps=100_000,
        processor=b'\x00' * 32,
        nonce=0
    )
    tx2.sign(Wallet().signing_key)
    tx2.serialize()

    currency_contract = 'currency'
    balances_hash = 'balances'

    balances_key = '{}{}{}{}{}'.format(currency_contract,
                                       config.INDEX_SEPARATOR,
                                       balances_hash,
                                       config.DELIMITER,
                                       w.verifying_key)

    driver = StateDriver()
    driver.set(balances_key, 1_000_000)
    driver.commit()

    return transaction_list_to_transaction_batch([tx.struct, tx2.struct], wallet=Wallet())

class TestExecution(TestCase):
    def setUp(self):
        self.client = ContractingClient()

    def tearDown(self):
        self.client.flush()

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

        tx = TransactionBuilder(
            sender='stu',
            contract='testing',
            function='set',
            kwargs={'var': 'jeff'},
            stamps=100_000,
            processor=b'\x00' * 32,
            nonce=0
        )
        tx.sign(Wallet().signing_key)
        tx.serialize()

        result = execution.execute_tx(self.client, tx.struct)

        print(result)

        self.assertEqual(result.status, 0)
        self.assertEqual(result.state[0].key, b'testing.v')
        self.assertEqual(result.state[0].value,  b'"jeff"')
        self.assertEqual(result.stampsUsed, 0)

    def test_generate_environment_creates_datetime_wrapped_object(self):
        timestamp = time.time()

        e = execution.generate_environment(MockDriver(), timestamp, b'A' * 32)

        t = datetime.utcfromtimestamp(timestamp)

        self.assertEqual(type(e['now']), Datetime)
        self.assertEqual(e['now'].year, t.year)
        self.assertEqual(e['now'].month, t.month)
        self.assertEqual(e['now'].day, t.day)
        self.assertEqual(e['now'].hour, t.hour)
        self.assertEqual(e['now'].minute, t.minute)
        self.assertEqual(e['now'].second, t.second)

    def test_generate_environment_creates_input_hash(self):
        timestamp = time.time()

        e = execution.generate_environment(MockDriver(), timestamp, b'A' * 32)

        self.assertEqual(e['__input_hash'], b'A' * 32)

    def test_generate_environment_creates_block_hash(self):
        timestamp = time.time()

        e = execution.generate_environment(MockDriver(), timestamp, b'A' * 32)

        self.assertEqual(e['block_hash'], MockDriver().latest_block_hash.hex())

    def test_generate_environment_creates_block_num(self):
        timestamp = time.time()

        e = execution.generate_environment(MockDriver(), timestamp, b'A' * 32)

        self.assertEqual(e['block_num'], MockDriver().latest_block_num)

    def test_execute_tx_batch_returns_all_transactions(self):
        test_contract = '''
v = Variable()

@construct
def seed():
    v.set('hello')

@export
def set(var):
    v.set(var)

@export
def get():
    return v.get()
        '''

        self.client.submit(test_contract, name='testing')

        tx = TransactionBuilder(
            sender='stu',
            contract='testing',
            function='set',
            kwargs={'var': 'howdy'},
            stamps=100_000,
            processor=b'\x00' * 32,
            nonce=0
        )
        tx.sign(Wallet().signing_key)
        tx.serialize()

        tx2 = TransactionBuilder(
            sender='stu',
            contract='testing',
            function='get',
            kwargs={},
            stamps=100_000,
            processor=b'\x00' * 32,
            nonce=0
        )
        tx2.sign(Wallet().signing_key)
        tx2.serialize()

        tx_batch = transaction_list_to_transaction_batch([tx.struct, tx2.struct], wallet=Wallet())

        results = execution.execute_tx_batch(self.client, MockDriver(), tx_batch, time.time(), b'A'*32)

        td1, td2 = results

        self.assertEqual(td1.status, 0)
        self.assertEqual(td1.state[0].key, b'testing.v')
        self.assertEqual(td1.state[0].value, b'"howdy"')
        self.assertEqual(td1.stampsUsed, 0)

        self.assertEqual(td2.status, 0)
        self.assertEqual(len(td2.state), 0)
        self.assertEqual(td2.stampsUsed, 0)

    def test_execute_work_multiple_transaction_batches_works(self):
        test_contract = '''
v = Variable()

@construct
def seed():
    v.set('hello')

@export
def set(var):
    v.set(var)

@export
def get():
    return v.get()
        '''

        self.client.submit(test_contract, name='testing')

        tx = TransactionBuilder(
            sender='stu',
            contract='testing',
            function='set',
            kwargs={'var': 'howdy'},
            stamps=100_000,
            processor=b'\x00' * 32,
            nonce=0
        )
        tx.sign(Wallet().signing_key)
        tx.serialize()

        tx2 = TransactionBuilder(
            sender='stu',
            contract='testing',
            function='get',
            kwargs={},
            stamps=100_000,
            processor=b'\x00' * 32,
            nonce=0
        )
        tx2.sign(Wallet().signing_key)
        tx2.serialize()

        tx_batch_1 = transaction_list_to_transaction_batch([tx.struct, tx2.struct], wallet=Wallet())

        tx = TransactionBuilder(
            sender='stu',
            contract='testing',
            function='set',
            kwargs={'var': '123'},
            stamps=100_000,
            processor=b'\x00' * 32,
            nonce=0
        )
        tx.sign(Wallet().signing_key)
        tx.serialize()

        tx2 = TransactionBuilder(
            sender='jeff',
            contract='testing',
            function='set',
            kwargs={'var': 'poo'},
            stamps=100_000,
            processor=b'\x00' * 32,
            nonce=0
        )
        tx2.sign(Wallet().signing_key)
        tx2.serialize()

        tx_batch_2 = transaction_list_to_transaction_batch([tx.struct, tx2.struct], wallet=Wallet())

        work = [
            (tx_batch_1.timestamp, tx_batch_1),
            (tx_batch_2.timestamp, tx_batch_2)
        ]

        sbc = execution.execute_work(self.client, MockDriver(), work, Wallet(), b'B'*32)

        sb1, sb2 = sbc

        td1, td2 = sb1.transactions
        self.assertEqual(td1.status, 0)
        self.assertEqual(td1.state[0].key, b'testing.v')
        self.assertEqual(td1.state[0].value, b'"howdy"')
        self.assertEqual(td1.stampsUsed, 0)

        self.assertEqual(td2.status, 0)
        self.assertEqual(len(td2.state), 0)
        self.assertEqual(td2.stampsUsed, 0)

        self.assertEqual(sb1.inputHash, tx_batch_1.inputHash)
        self.assertEqual(sb1.subBlockNum, 0)
        self.assertEqual(sb1.prevBlockHash, b'B'*32)

        td1, td2 = sb2.transactions
        self.assertEqual(td1.status, 0)
        self.assertEqual(td1.state[0].key, b'testing.v')
        self.assertEqual(td1.state[0].value, b'"123"')
        self.assertEqual(td1.stampsUsed, 0)

        self.assertEqual(td2.status, 0)
        self.assertEqual(td2.state[0].key, b'testing.v')
        self.assertEqual(td2.state[0].value, b'"poo"')
        self.assertEqual(td2.stampsUsed, 0)

        self.assertEqual(sb2.inputHash, tx_batch_2.inputHash)
        self.assertEqual(sb2.subBlockNum, 1)
        self.assertEqual(sb2.prevBlockHash, b'B' * 32)


bootnodes = ['ipc:///tmp/n2', 'ipc:///tmp/n3']

mnw1 = Wallet()

dw1 = Wallet()


constitution = {
    "masternodes": {
        "vk_list": [
            mnw1.verifying_key,
        ],
        "min_quorum": 1
    },
    "delegates": {
        "vk_list": [
            dw1.verifying_key,
        ],
        "min_quorum": 1
    },
    "witnesses": {},
    "schedulers": {},
    "notifiers": {},
    "enable_stamps": False,
    "enable_nonces": False
}

class TestDelegate(TestCase):
    def setUp(self):
        self.ctx = zmq.asyncio.Context()
        self.client = ContractingClient()
        self.client.flush()

    def tearDown(self):
        self.ctx.destroy()
        self.client.flush()

    def test_init(self):
        b = Delegate(socket_base='tcp://127.0.0.1', wallet=Wallet(), ctx=self.ctx, bootnodes=bootnodes,
                     constitution=constitution)

    def test_did_sign_block_false_if_no_pending_sbcs(self):
        b = Delegate(socket_base='tcp://127.0.0.1', wallet=Wallet(), ctx=self.ctx, bootnodes=bootnodes,
                     constitution=constitution)

        self.assertFalse(b.did_sign_block(None))

    def test_did_sign_block_false_if_missing_any_merkle_roots(self):
        b = Delegate(socket_base='tcp://127.0.0.1', wallet=Wallet(), ctx=self.ctx, bootnodes=bootnodes,
                     constitution=constitution)

        block = random_block()

        # Add one root but not the other
        b.pending_sbcs.add(block.subBlocks[0].merkleRoot)

        self.assertFalse(b.did_sign_block(block))

    def test_did_sign_block_true_if_all_merkle_roots_in_pending(self):
        b = Delegate(socket_base='tcp://127.0.0.1', wallet=Wallet(), ctx=self.ctx, bootnodes=bootnodes,
                     constitution=constitution)

        block = random_block()

        # Add one root but not the other
        b.pending_sbcs.add(block.subBlocks[0].merkleRoot)
        b.pending_sbcs.add(block.subBlocks[1].merkleRoot)

        self.assertTrue(b.did_sign_block(block))

    def test_process_nbn_commits_changes_if_did_sign_block(self):
        b = Delegate(socket_base='tcp://127.0.0.1', wallet=Wallet(), ctx=self.ctx, bootnodes=bootnodes,
                     constitution=constitution)

        block = random_block()

        # Add one root but not the other
        b.pending_sbcs.add(block.subBlocks[0].merkleRoot)
        b.pending_sbcs.add(block.subBlocks[1].merkleRoot)

        b.client.raw_driver.set('A', 'B')
        self.assertIsNone(b.client.raw_driver.get_direct('A'))

        b.process_new_block(block)

        self.assertEqual(b.client.raw_driver.get(b'A'), 'B')

    def test_process_nbn_updates_state_with_block_if_did_not_sign_block(self):
        b = Delegate(socket_base='tcp://127.0.0.1', wallet=Wallet(), ctx=self.ctx, bootnodes=bootnodes,
                     constitution=constitution)

        block = random_block()

        k = block.subBlocks[0].transactions[0].state[0].key
        v = block.subBlocks[0].transactions[0].state[0].value

        self.assertIsNone(b.client.raw_driver.get_direct(k))

        b.process_new_block(block)

        self.assertEqual(b.client.raw_driver.get_direct(k), v)

    def test_run_single_block_mock(self):
        b = Delegate(socket_base='ipc:///tmp/n2', wallet=Wallet(), ctx=self.ctx, bootnodes=bootnodes,
                     constitution=constitution)

        gb = lamden.nodes.masternode.masternode.get_genesis_block()
        gb = canonical.dict_to_capnp_block(gb)

        # Put the genesis block in here so we start immediately
        b.nbn_inbox.q.append(gb)

        b.running = True

        # Add a single peer that we control
        b.parameters.sockets = {
            mnw1.verifying_key: 'ipc:///tmp/n1'
        }

        put_test_contract(self.client)

        b.work_inbox.work[mnw1.verifying_key] = get_tx_batch()

        async def stop():
            await asyncio.sleep(1)
            b.running = False
            b.nbn_inbox.q.append(gb)

        loop = asyncio.get_event_loop()

        tasks = asyncio.gather(
            b.run(),
            stop()
        )

        loop.run_until_complete(tasks)
