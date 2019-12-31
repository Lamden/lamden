from unittest import TestCase

from cilantro_ee.nodes.masternode.new_ws import WebServer
from cilantro_ee.core.crypto.wallet import Wallet
from contracting.client import ContractingClient


class TestClassWebserver(TestCase):
    def setUp(self):
        self.w = Wallet()
        self.ws = WebServer(wallet=self.w, contracting_client=ContractingClient())
        self.ws.client.flush()

    def tearDown(self):
        self.ws.client.flush()

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

        self.ws.nonce_manager.set_pending_nonce(self.w.verifying_key(), w2.verifying_key(), 123)

        _, response = self.ws.app.test_client.get('/nonce/{}'.format(w2.verifying_key().hex()))

        expected = {'nonce': 123, 'processor': self.w.verifying_key().hex(), 'sender': w2.verifying_key().hex()}

        self.assertDictEqual(response.json, expected)

    def test_get_nonce_pending_nonce_is_none_but_nonce_is_not_returns_nonce(self):
        w2 = Wallet()

        self.ws.nonce_manager.set_nonce(self.w.verifying_key(), w2.verifying_key(), 555)

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
        pass

    def test_get_block_by_num_that_exists(self):
        pass

    def test_get_block_by_num_that_doesnt_exist_returns_error(self):
        pass

    def test_get_block_by_hash_that_exists(self):
        pass

    def test_get_block_by_hash_that_doesnt_exist_returns_error(self):
        pass

