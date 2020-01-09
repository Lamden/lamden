from unittest import TestCase
from cilantro_ee.nodes.delegate.delegate import Delegate
from cilantro_ee.nodes.delegate import execution
from contracting.client import ContractingClient
from contracting.stdlib.bridge.time import Datetime
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.crypto.transaction import TransactionBuilder
import time
from cilantro_ee.crypto.transaction_batch import transaction_list_to_transaction_batch


class MockDriver:
    def __init__(self):
        self.latest_block_hash = b'\x00' * 32
        self.latest_block_num = 999


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

        result = execution.execute_tx(self.client, tx.struct)

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
        tx.sign(Wallet().signing_key())
        tx.serialize()

        tx2 = TransactionBuilder(
            sender='jeff',
            contract='testing',
            function='get',
            kwargs={'var': 'poo'},
            stamps=100_000,
            processor=b'\x00' * 32,
            nonce=0
        )
        tx2.sign(Wallet().signing_key())
        tx2.serialize()

        tx_batch_2 = transaction_list_to_transaction_batch([tx.struct, tx2.struct], wallet=Wallet())

        work = [
            (tx_batch_1.timestamp, tx_batch_1),
            (tx_batch_2.timestamp, tx_batch_2)
        ]

        sbc = execution.execute_work(self.client, MockDriver(), work, Wallet(), b'B'*32)

        print(sbc[0])