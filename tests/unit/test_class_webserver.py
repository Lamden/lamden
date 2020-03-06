from unittest import TestCase

from cilantro_ee.nodes.masternode.webserver import WebServer
from cilantro_ee.crypto.wallet import Wallet
from contracting.client import ContractingClient
from cilantro_ee.storage import BlockchainDriver
from cilantro_ee.storage import CilantroStorageDriver
from cilantro_ee.crypto.transaction import TransactionBuilder
from contracting import config
from cilantro_ee.messages.capnp_impl import capnp_struct as schemas
import os
import capnp

transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')

n = BlockchainDriver()


def make_good_tx(processor):
    w = Wallet()
    balances_key = '{}{}{}{}{}'.format('currency',
                                       config.INDEX_SEPARATOR,
                                       'balances',
                                       config.DELIMITER,
                                       w.verifying_key().hex())
    n.set(balances_key, 500000)
    tx = TransactionBuilder(w.verifying_key(),
                            contract='currency',
                            function='transfer',
                            kwargs={'amount': 10, 'to': 'jeff'},
                            stamps=500000,
                            processor=processor,
                            nonce=0)

    tx.sign(w.signing_key())
    tx_bytes = tx.serialize()
    return tx_bytes


def make_bad_tx():
    w = Wallet()
    balances_key = '{}{}{}{}{}'.format('currency',
                                       config.INDEX_SEPARATOR,
                                       'balances',
                                       config.DELIMITER,
                                       w.verifying_key().hex())
    n.set(balances_key, 500000)
    tx = TransactionBuilder(w.verifying_key(),
                            contract='currency',
                            function='transfer',
                            kwargs={'amount': 10, 'to': 'jeff'},
                            stamps=500000,
                            processor=b'\x00' * 32,
                            nonce=0)

    tx.sign(w.signing_key())
    tx_bytes = tx.serialize()
    #tx_struct = transaction_capnp.Transaction.from_bytes_packed(tx_bytes)
    return tx_bytes


class TestClassWebserver(TestCase):
    def setUp(self):
        self.w = Wallet()

        self.blocks = CilantroStorageDriver(key=self.w.verifying_key())
        self.driver = BlockchainDriver()

        self.ws = WebServer(
            wallet=self.w,
            contracting_client=ContractingClient(),
            blocks=self.blocks,
            driver=n
        )
        self.ws.client.flush()
        self.ws.blocks.drop_collections()

    def tearDown(self):
        self.ws.client.flush()
        self.ws.blocks.drop_collections()

    def test_ping(self):
        _, response = self.ws.app.test_client.get('/ping')
        self.assertDictEqual(response.json, {'status': 'online'})

    def test_get_id(self):
        _, response = self.ws.app.test_client.get('/id')
        self.assertDictEqual(response.json, {'verifying_key': self.w.verifying_key().hex()})

    def test_get_nonce_pending_nonce_is_none_returns_0(self):
        w2 = Wallet()
        _, response = self.ws.app.test_client.get('/nonce/{}'.format(w2.verifying_key().hex()))

        expected = {'nonce': 0, 'processor': self.w.verifying_key().hex(), 'sender': w2.verifying_key().hex()}

        self.assertDictEqual(response.json, expected)

    def test_get_nonce_pending_nonce_is_not_none_returns_pending_nonce(self):
        w2 = Wallet()

        self.ws.driver.set_pending_nonce(self.w.verifying_key(), w2.verifying_key(), 123)

        _, response = self.ws.app.test_client.get('/nonce/{}'.format(w2.verifying_key().hex()))

        expected = {'nonce': 123, 'processor': self.w.verifying_key().hex(), 'sender': w2.verifying_key().hex()}

        self.assertDictEqual(response.json, expected)

    def test_get_nonce_pending_nonce_is_none_but_nonce_is_not_returns_nonce(self):
        w2 = Wallet()

        self.ws.driver.set_nonce(self.w.verifying_key(), w2.verifying_key(), 555)

        _, response = self.ws.app.test_client.get('/nonce/{}'.format(w2.verifying_key().hex()))

        expected = {'nonce': 555, 'processor': self.w.verifying_key().hex(), 'sender': w2.verifying_key().hex()}

        self.assertDictEqual(response.json, expected)

    def test_get_contracts_returns_list_of_contracts(self):
        _, response = self.ws.app.test_client.get('/contracts')

        self.assertDictEqual(response.json, {'contracts': ['submission']})

    def test_get_contract_returns_contract_code(self):
        _, response = self.ws.app.test_client.get('/contracts/submission')

        f = open(self.ws.client.submission_filename)
        code = f.read()
        f.close()

        expected = {'name': 'submission', 'code': code}

        self.assertDictEqual(response.json, expected)

    def test_get_contract_that_does_not_exist_returns_error(self):
        _, response = self.ws.app.test_client.get('/contracts/blah')

        self.assertDictEqual(response.json, {'error': 'blah does not exist'})

    def test_get_contract_methods_returns_all_methods(self):
        _, response = self.ws.app.test_client.get('/contracts/submission/methods')

        self.assertDictEqual(response.json, {'methods': [{'name': 'submit_contract', 'arguments':
            ['name', 'code', 'owner', 'constructor_args']}]})

    def test_get_contract_method_returns_error_if_does_not_exist(self):
        _, response = self.ws.app.test_client.get('/contracts/blah/methods')

        self.assertDictEqual(response.json, {'error': 'blah does not exist'})

    def test_get_variable_returns_value_if_it_exists(self):
        code = '''
v = Variable()

@construct
def seed():
    v.set(12345)

@export
def get():
    return v.get()
        '''

        self.ws.client.submit(f=code, name='testing')

        _, response = self.ws.app.test_client.get('/contracts/testing/v')

        self.assertDictEqual(response.json, {'value': 12345})

    def test_get_variables_returns_variable_list(self):
            code = '''
v = Variable()
howdy = Variable()
h = Hash()
hash2 = Hash()

@construct
def seed():
    a = 123
    v.set(12345)

@export
def get():
    return v.get()
        '''

            self.ws.client.submit(f=code, name='testing')

            _, response = self.ws.app.test_client.get('/contracts/testing/variables')

            expected = {
                'variables': ['v', 'howdy'],
                'hashes': ['h', 'hash2']
            }

            self.assertDictEqual(response.json, expected)

    def test_get_variable_returns_error_if_contract_does_not_exist(self):
        _, response = self.ws.app.test_client.get('/contracts/blah/v')

        self.assertDictEqual(response.json, {'error': 'blah does not exist'})

    def test_get_variable_returns_none_if_variable_does_not_exist(self):
        code = '''
v = Variable()

@construct
def seed():
    v.set(12345)

@export
def get():
    return v.get()
        '''

        self.ws.client.submit(f=code, name='testing')

        _, response = self.ws.app.test_client.get('/contracts/testing/x')

        self.assertDictEqual(response.json, {'value': None})

    def test_get_variable_works_for_single_key(self):
        code = '''
h = Hash()

@construct
def seed():
    h['stu'] = 99999

@export
def get():
    return h['stu']
        '''

        self.ws.client.submit(f=code, name='testing')

        _, response = self.ws.app.test_client.get('/contracts/testing/h?key=stu')

        self.assertDictEqual(response.json, {'value': 99999})

    def test_get_variable_works_for_multihashes(self):
        code = '''
h = Hash()

@construct
def seed():
    h['stu'] = 99999
    h['stu', 'hello', 'jabroni'] = 77777

@export
def get():
    return h['stu']
        '''

        self.ws.client.submit(f=code, name='testing')

        _, response = self.ws.app.test_client.get('/contracts/testing/h?key=stu,hello,jabroni')

        self.assertDictEqual(response.json, {'value': 77777})

    def test_get_variable_multihash_returns_none(self):
        code = '''
h = Hash()

@construct
def seed():
    h['stu'] = 99999
    h['stu', 'hello', 'jabroni'] = 77777

@export
def get():
    return h['stu']
        '''

        self.ws.client.submit(f=code, name='testing')

        _, response = self.ws.app.test_client.get('/contracts/testing/h?key=notstu,hello,jabroni')

        self.assertDictEqual(response.json, {'value': None})

        _, response = self.ws.app.test_client.get('/contracts/testing/h?key=notstu')

        self.assertDictEqual(response.json, {'value': None})

    def test_get_latest_block(self):
        block = {
            'hash': 'a',
            'blockNum': 1,
            'data': 'woop'
        }

        self.ws.blocks.put(block)

        block2 = {
            'hash': 'abb',
            'blockNum': 1000,
            'data': 'woop2'
        }

        self.ws.blocks.put(block2)

        _, response = self.ws.app.test_client.get('/latest_block')
        self.assertDictEqual(response.json, {'hash': 'abb', 'blockNum': 1000, 'data': 'woop2'})

    def test_get_latest_block_num(self):
        self.ws.driver.set_latest_block_num(1234)

        _, response = self.ws.app.test_client.get('/latest_block_num')
        self.assertDictEqual(response.json, {'latest_block_number': 1234})

    def test_get_latest_block_hash(self):
        h = '0' * 64
        self.ws.driver.set_latest_block_hash(h)

        _, response = self.ws.app.test_client.get('/latest_block_hash')

        self.assertDictEqual(response.json, {'latest_block_hash': h})

    def test_get_block_by_num_that_exists(self):
        block = {
            'hash': '1234',
            'blockNum': 1,
            'data': 'woop'
        }

        self.ws.blocks.put(block)

        _, response = self.ws.app.test_client.get('/blocks?num=1')

        del block['_id']

        self.assertDictEqual(response.json, block)

    def test_get_block_by_num_that_doesnt_exist_returns_error(self):
        _, response = self.ws.app.test_client.get('/blocks?num=1000')

        self.assertDictEqual(response.json, {'error': 'Block not found.'})

    def test_get_block_by_hash_that_exists(self):
        h = '1234'

        block = {
            'hash': h,
            'blockNum': 1,
            'data': 'woop'
        }

        self.ws.blocks.put(block)

        expected = {
            'hash': h,
            'blockNum': 1,
            'data': 'woop'
        }

        del block['_id']

        _, response = self.ws.app.test_client.get(f'/blocks?hash={h}')
        self.assertDictEqual(response.json, expected)

    def test_get_block_by_hash_that_doesnt_exist_returns_error(self):
        _, response = self.ws.app.test_client.get('/blocks?hash=zzz')
        self.assertDictEqual(response.json, {'error': 'Block not found.'})

    def test_get_block_no_args_returns_error(self):
        _, response = self.ws.app.test_client.get('/blocks')
        self.assertDictEqual(response.json, {'error': 'No number or hash provided.'})

    def test_bad_transaction_returns_a_TransactionException(self):
        _, response = self.ws.app.test_client.post('/', data=make_bad_tx())
        self.assertDictEqual(response.json, {'error': 'Transaction processor does not match expected processor.'})

    def test_good_transaction_is_put_into_queue(self):
        self.assertEqual(len(self.ws.queue), 0)

        _, response = self.ws.app.test_client.post('/', data=make_good_tx(self.w.verifying_key()))

        self.assertEqual(len(self.ws.queue), 1)

    def test_submit_transaction_error_if_queue_full(self):
        self.ws.queue.extend(range(10_000))
        _, response = self.ws.app.test_client.post('/', data=make_good_tx(self.w.verifying_key()))

        self.assertDictEqual(response.json, {'error': 'Queue full. Resubmit shortly.'})

    def test_submit_transaction_error_if_tx_malformed(self):
        pass

    def test_get_tx_by_hash_if_it_exists(self):
        b = b'\x00' * 32

        tx = {
            'hash': b,
            'some': 'data'
        }

        expected = {
            'hash': b.hex(),
            'some': 'data'
        }

        self.ws.blocks.put(tx, collection=self.ws.blocks.TX)

        del tx['_id']

        _, response = self.ws.app.test_client.get(f'/tx?hash={b.hex()}')
        self.assertDictEqual(response.json, expected)

