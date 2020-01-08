from unittest import TestCase
from cilantro_ee.nodes.delegate.delegate import BlockManager
from cilantro_ee.crypto.wallet import Wallet
from tests.utils.constitution_builder import ConstitutionBuilder
from cilantro_ee.contracts.sync import extract_vk_args, submit_vkbook
from contracting.client import ContractingClient
from cilantro_ee.storage.vkbook import VKBook
from cilantro_ee.crypto.transaction_batch import transaction_list_to_transaction_batch
from cilantro_ee.crypto.transaction import TransactionBuilder
import zmq.asyncio
import asyncio

from contracting.stdlib.bridge.time import Datetime
from datetime import datetime
from contracting.db.encoder import encode


class TestBlockManager(TestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.ctx = zmq.asyncio.Context()
        self.const_builder = ConstitutionBuilder(10, 10, 10, 10, False, False)
        book = self.const_builder.get_constitution()
        extract_vk_args(book)
        submit_vkbook(book, overwrite=True)
        self.client = ContractingClient()

    def tearDown(self):
        self.ctx.destroy()
        self.loop.stop()
        self.client.flush()

    def test_init(self):
        b = BlockManager(socket_base='tcp://127.0.0.1', wallet=Wallet(), ctx=self.ctx, contacts=VKBook())

    def test_execute_work_single_transaction(self):
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
            kwargs={'var': 'jeff'},
            stamps=100_000,
            processor=b'\x00'*32,
            nonce=0
        )
        tx.sign(Wallet().signing_key())
        tx.serialize()

        tx_batch = transaction_list_to_transaction_batch([tx.struct], wallet=Wallet())

        b = BlockManager(socket_base='tcp://127.0.0.1', wallet=Wallet(), ctx=self.ctx, contacts=VKBook())

        b.execute_work([(1, tx_batch)])

    def test_execute_multiple_tx_in_batch_returns_correct_sbc(self):
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
        tx.sign(Wallet().signing_key())
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
        tx2.sign(Wallet().signing_key())
        tx2.serialize()

        tx_batch = transaction_list_to_transaction_batch([tx.struct, tx2.struct], wallet=Wallet())
        w = Wallet()
        b = BlockManager(socket_base='tcp://127.0.0.1', wallet=w, ctx=self.ctx, contacts=VKBook())

        results = b.execute_work([(tx_batch.timestamp, tx_batch)])

        # Test that there is a state change on the 1st tx
        tx = results[0].transactions[0]
        self.assertEqual(tx.state[0].key, b'testing.v')
        self.assertEqual(tx.state[0].value, b'"howdy"')

        self.assertEqual(results[0].inputHash, tx_batch.inputHash)
        self.assertEqual(results[0].prevBlockHash, b'\x00'*32)
        self.assertEqual(results[0].signer, w.verifying_key())

    def test_environment_variables_are_working_as_they_should(self):
        test_contract = '''
a = Variable()
b = Variable()
c = Variable()

@export
def capture():
    a.set(block_hash)
    b.set(block_num)
    c.set(now)
        '''

        self.client.submit(test_contract, name='testing')

        tx = TransactionBuilder(
            sender='stu',
            contract='testing',
            function='capture',
            kwargs={},
            stamps=100_000,
            processor=b'\x00' * 32,
            nonce=0
        )
        tx.sign(Wallet().signing_key())
        tx.serialize()

        tx_batch = transaction_list_to_transaction_batch([tx.struct], wallet=Wallet())
        w = Wallet()
        b = BlockManager(socket_base='tcp://127.0.0.1', wallet=w, ctx=self.ctx, contacts=VKBook())

        now = Datetime._from_datetime(
            datetime.utcfromtimestamp(tx_batch.timestamp)
        )

        results = b.execute_work([(tx_batch.timestamp, tx_batch)])

        tx = results[0].transactions[0]

        a, b, c = tx.state

        self.assertEqual(a.key, b'testing.a')
        self.assertEqual(a.value, b'"0000000000000000000000000000000000000000000000000000000000000000"')

        self.assertEqual(b.key, b'testing.b')
        self.assertEqual(b.value, b'0')

        self.assertEqual(c.key, b'testing.c')
        self.assertEqual(c.value, encode(now).encode())

    def test_build_sbc_from_work_results(self):
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
            kwargs={'var': 'jeff'},
            stamps=100_000,
            processor=b'\x00' * 32,
            nonce=0
        )
        tx.sign(Wallet().signing_key())
        tx.serialize()

        tx_batch = transaction_list_to_transaction_batch([tx.struct], wallet=Wallet())

        b = BlockManager(socket_base='tcp://127.0.0.1', wallet=Wallet(), ctx=self.ctx, contacts=VKBook())


        print(sbc)