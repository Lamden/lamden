from unittest import TestCase

from lamden.nodes.masternode.webserver import WebServer
from lamden.crypto.wallet import Wallet
from contracting.client import ContractingClient
from contracting.db.driver import ContractDriver, decode, encode
from lamden.storage import BlockStorage
from lamden.crypto.transaction import build_transaction
from lamden import storage

n = ContractDriver()


class TestClassWebserver(TestCase):
    def setUp(self):
        self.w = Wallet()

        self.blocks = BlockStorage()
        self.driver = ContractDriver()

        self.ws = WebServer(
            wallet=self.w,
            contracting_client=ContractingClient(),
            blocks=self.blocks,
            driver=n
        )
        self.ws.client.flush()
        self.ws.blocks.flush()
        self.ws.driver.flush()

    def tearDown(self):
        self.ws.client.flush()
        self.ws.blocks.flush()
        self.ws.driver.flush()

    def test_ping(self):
        _, response = self.ws.app.test_client.get('/ping')
        self.assertDictEqual(response.json, {'status': 'online'})

    def test_get_id(self):
        _, response = self.ws.app.test_client.get('/id')
        self.assertDictEqual(response.json, {'verifying_key': self.w.verifying_key})

    def test_get_nonce_pending_nonce_is_none_returns_0(self):
        w2 = Wallet()
        _, response = self.ws.app.test_client.get('/nonce/{}'.format(w2.verifying_key))

        expected = {'nonce': 0, 'processor': self.w.verifying_key, 'sender': w2.verifying_key}

        self.assertDictEqual(response.json, expected)

    def test_get_nonce_pending_nonce_is_not_none_returns_pending_nonce(self):
        w2 = Wallet()

        self.ws.nonces.set_pending_nonce(
            sender=w2.verifying_key,
            processor=self.w.verifying_key,
            value=123
        )

        _, response = self.ws.app.test_client.get('/nonce/{}'.format(w2.verifying_key))

        expected = {'nonce': 123, 'processor': self.w.verifying_key, 'sender': w2.verifying_key}

        self.assertDictEqual(response.json, expected)

    def test_get_nonce_pending_nonce_is_none_but_nonce_is_not_returns_nonce(self):
        w2 = Wallet()

        self.ws.nonces.set_nonce(processor=self.w.verifying_key, sender=w2.verifying_key, value=555)

        _, response = self.ws.app.test_client.get('/nonce/{}'.format(w2.verifying_key))

        expected = {'nonce': 555, 'processor': self.w.verifying_key, 'sender': w2.verifying_key}

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

        self.assertDictEqual(response.json,
            {
                'methods': [
                    {
                        'name': 'submit_contract',
                        'arguments': [
                            {
                                'name': 'name',
                                'type': 'str'
                            },
                            {
                                'name': 'code',
                                'type': 'str'
                            },
                            {
                                'name': 'owner',
                                'type': 'Any'
                            },
                            {
                                'name':'constructor_args',
                                'type': 'dict'
                            }
                        ]
                    }
                ]
            })

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

    def test_get_variables_returns_error_if_contract_does_not_exist(self):
        _, response = self.ws.app.test_client.get('/contracts/blah/variables')

        self.assertDictEqual(response.json, {'error': 'blah does not exist'})

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
            'number': 1,
            'data': 'woop'
        }

        self.ws.blocks.put(block)

        block2 = {
            'hash': 'abb',
            'number': 1000,
            'data': 'woop2'
        }

        self.ws.blocks.put(block2)

        _, response = self.ws.app.test_client.get('/latest_block')
        self.assertDictEqual(response.json, {'hash': 'abb', 'number': 1000, 'data': 'woop2'})

    def test_get_latest_block_num(self):
        storage.set_latest_block_height(1234, self.ws.driver)

        _, response = self.ws.app.test_client.get('/latest_block_num')
        self.assertDictEqual(response.json, {'latest_block_number': 1234})

    def test_get_latest_block_hash(self):
        h = '0' * 64
        storage.set_latest_block_hash(h, self.ws.driver)

        _, response = self.ws.app.test_client.get('/latest_block_hash')

        self.assertDictEqual(response.json, {'latest_block_hash': h})

    def test_get_block_by_num_that_exists(self):
        block = {
            'hash': '1234',
            'number': 1,
            'data': 'woop'
        }

        self.ws.blocks.put(block)

        _, response = self.ws.app.test_client.get('/blocks?num=1')

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

        _, response = self.ws.app.test_client.get(f'/blocks?hash={h}')
        self.assertDictEqual(response.json, expected)

    def test_get_block_by_hash_that_doesnt_exist_returns_error(self):
        _, response = self.ws.app.test_client.get('/blocks?hash=zzz')
        self.assertDictEqual(response.json, {'error': 'Block not found.'})

    def test_get_block_no_args_returns_error(self):
        _, response = self.ws.app.test_client.get('/blocks')
        self.assertDictEqual(response.json, {'error': 'No number or hash provided.'})

    def test_bad_transaction_returns_a_TransactionException(self):
        tx = build_transaction(
            wallet=Wallet(),
            processor='b' * 64,
            stamps=123,
            nonce=0,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 123,
                'to': 'jeff'
            }
        )
        _, response = self.ws.app.test_client.post('/', data=tx)
        self.assertDictEqual(response.json, {'error': 'Transaction processor does not match expected processor.'})

    def test_good_transaction_is_put_into_queue(self):
        self.assertEqual(len(self.ws.queue), 0)

        w = Wallet()

        self.ws.client.set_var(
            contract='currency',
            variable='balances',
            arguments=[w.verifying_key],
            value=1_000_000
        )

        self.ws.client.set_var(
            contract='stamp_cost',
            variable='S',
            arguments=['value'],
            value=1_000_000
        )

        tx = build_transaction(
            wallet=w,
            processor=self.ws.wallet.verifying_key,
            stamps=6000,
            nonce=0,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 123,
                'to': 'jeff'
            }
        )

        _, response = self.ws.app.test_client.post('/', data=tx)

        self.assertEqual(len(self.ws.queue), 1)

    def test_fixed_objects_do_not_fail_signature(self):
        self.assertEqual(len(self.ws.queue), 0)

        w = Wallet()

        self.ws.client.set_var(
            contract='currency',
            variable='balances',
            arguments=[w.verifying_key],
            value=1_000_000
        )

        self.ws.client.set_var(
            contract='stamp_cost',
            variable='S',
            arguments=['value'],
            value=1_000_000
        )

        tx = build_transaction(
            wallet=w,
            processor=self.ws.wallet.verifying_key,
            stamps=6000,
            nonce=0,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': {'__fixed__': '1.0'},
                'to': 'jeff'
            }
        )

        _, response = self.ws.app.test_client.post('/', data=tx)

        self.assertEqual(len(self.ws.queue), 1)

    def test_submit_transaction_error_if_queue_full(self):
        self.ws.queue.extend(range(10_000))

        tx = build_transaction(
            wallet=Wallet(),
            processor=self.ws.wallet.verifying_key,
            stamps=123,
            nonce=0,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 123,
                'to': 'jeff'
            }
        )

        _, response = self.ws.app.test_client.post('/', data=tx)

        self.assertDictEqual(response.json, {'error': 'Queue full. Resubmit shortly.'})

        self.ws.queue.clear()

    def test_get_tx_by_hash_if_it_exists(self):
        b = '0' * 64

        tx = {
            'hash': b,
            'some': 'data'
        }

        expected = {
            'hash': b,
            'some': 'data'
        }

        self.ws.blocks.put(tx, collection=self.ws.blocks.TX)

        _, response = self.ws.app.test_client.get(f'/tx?hash={b}')
        self.assertDictEqual(response.json, expected)

    def test_malformed_tx_returns_error(self):
        tx = b'"df:'

        _, response = self.ws.app.test_client.post('/', data=tx)

        self.assertDictEqual(response.json, {'error': 'Malformed request body.'})

    def test_tx_with_error_returns_exception(self):
        tx = build_transaction(
            wallet=Wallet(),
            processor=self.ws.wallet.verifying_key,
            stamps=123,
            nonce=0,
            contract='currency',
            function='transfer',
            kwargs={
                'amount': 123,
                'to': 'jeff'
            }
        )

        tx = decode(tx)
        tx['payload']['stamps_supplied'] = -123
        tx = encode(tx)

        _, response = self.ws.app.test_client.post('/', data=tx)

        self.assertDictEqual(response.json, {'error': 'Transaction is not formatted properly.'})

    def test_get_constitution_returns_correct_state(self):
        self.ws.client.set_var(
            contract='masternodes',
            variable='S',
            arguments=['members'],
            value=['1', '2', '3']
        )

        self.ws.client.set_var(
            contract='delegates',
            variable='S',
            arguments=['members'],
            value=['4', '5', '6']
        )

        self.ws.client.raw_driver.commit()

        _, response = self.ws.app.test_client.get('/constitution')

        self.assertDictEqual(response.json, {
            'masternodes': ['1', '2', '3'],
            'delegates': ['4', '5', '6'],
        })

    def test_error_returned_if_tx_hash_not_provided(self):
        _, response = self.ws.app.test_client.get('/tx')

        self.assertDictEqual(response.json, {'error': 'No tx hash provided.'})

    def test_error_returned_if_tx_hash_malformed(self):
        _, response = self.ws.app.test_client.get('/tx?hash=hello')

        self.assertDictEqual(response.json, {'error': 'Malformed hash.'})

    def test_error_returned_if_no_tx_hash(self):
        _, response = self.ws.app.test_client.get('/tx?hash=' + 'a' * 64)

        self.assertDictEqual(response.json, {'error': 'Transaction not found.'})

    def test_js_encoded_tx_works(self):
        pass