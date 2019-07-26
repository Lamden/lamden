from unittest import TestCase
from contracting.webserver import app, client
import json
import aiohttp


class TestWebserver(TestCase):
    def tearDown(self):
        client.flush()

    def test_ping_api(self):
        _, response = app.test_client.get('/')
        self.assertEqual(response.status, 200)

    def test_get_all_contracts(self):
        _, response = app.test_client.get('/contracts')
        contracts = response.json.get('contracts')
        self.assertListEqual(['submission'], contracts)

    # def test_get_submission_code(self):
    #     with open('../contracting/contracting/contracts/submission.s.py') as f:
    #         contract = f.read()
    #
    #     _, response = app.test_client.get('/contracts/submission')
    #
    #     code = response.json.get('code')
    #
    #     self.assertEqual(contract, code)
    #     self.assertEqual(response.status, 200)
    #
    def test_get_non_existent_contract(self):
        _, response = app.test_client.get('/contracts/hoooooooopla')
        self.assertEqual(response.status, 404)

        error_message = response.json.get('error')

        self.assertEqual(error_message, 'hoooooooopla does not exist')

    def test_get_non_existent_contract_methods(self):
        _, response = app.test_client.get('/contracts/huuuuuuuuupluh/methods')

        self.assertEqual(response.status, 404)

        error_message = response.json.get('error')

        self.assertEqual(error_message, 'huuuuuuuuupluh does not exist')

    # def test_contract_submission_hits_raw_database(self):
    #     with open('./test_sys_contracts/currency.s.py') as f:
    #         contract = f.read()
    #
    #     payload = {'name': 'currency', 'code': contract}
    #
    #     _, response = app.test_client.post('/submit', data=json.dumps(payload))
    #
    #     self.assertEqual(response.status, 200)
    #
    #     currency = client.raw_driver.get_contract('currency')
    #
    #     self.assertIsNotNone(currency)
    #
    # def test_get_variable(self):
    #     with open('./test_sys_contracts/currency.s.py') as f:
    #         contract = f.read()
    #
    #     payload = {'name': 'currency', 'code': contract}
    #
    #     _, response = app.test_client.post('/submit', data=json.dumps(payload))
    #
    #     _, response = app.test_client.get('/contracts/currency/seed_amount')
    #
    #     self.assertEqual(response.status, 200)
    #     self.assertEqual(response.json.get('value'), 1000000)
    #
    def test_get_variable_from_non_existent_contract(self):
        _, response = app.test_client.get('/contracts/currency/seed_amount')

        self.assertEqual(response.status, 404)
    #
    # def test_get_non_existent_variable_from_contract(self):
    #     with open('./test_sys_contracts/currency.s.py') as f:
    #         contract = f.read()
    #
    #     payload = {'name': 'currency', 'code': contract}
    #
    #     _, response = app.test_client.post('/submit', data=json.dumps(payload))
    #
    #     _, response = app.test_client.get('/contracts/currency/hoooooooplah')
    #
    #     self.assertEqual(response.status, 404)
    #     self.assertEqual(response.json.get('value'), None)
    #
    # def test_get_hash_value(self):
    #     with open('./test_sys_contracts/currency.s.py') as f:
    #         contract = f.read()
    #
    #     payload = {'name': 'currency', 'code': contract}
    #
    #     _, response = app.test_client.post('/submit', data=json.dumps(payload))
    #
    #     _, response = app.test_client.get(
    #         '/contracts/currency/balances?key=324ee2e3544a8853a3c5a0ef0946b929aa488cbe7e7ee31a0fef9585ce398502'
    #     )
    #
    #     self.assertEqual(response.status, 200)
    #     self.assertEqual(response.json.get('value'), 1000000)
    #
    def test_get_hash_from_non_existent_contract(self):
        _, response = app.test_client.get(
            '/contracts/currency/balances?key=324ee2e3544a8853a3c5a0ef0946b929aa488cbe7e7ee31a0fef9585ce398502'
        )

        self.assertEqual(response.status, 404)
        self.assertEqual(response.json.get('value'), None)
    #
    # def test_get_non_existent_hash_from_contract(self):
    #     with open('./test_sys_contracts/currency.s.py') as f:
    #         contract = f.read()
    #
    #     payload = {'name': 'currency', 'code': contract}
    #
    #     _, response = app.test_client.post('/submit', data=json.dumps(payload))
    #
    #     _, response = app.test_client.get(
    #         '/contracts/currency/balances?key=ZZZZZZZZZZZZZZZZZZZZZZ'
    #     )
    #
    #     self.assertEqual(response.status, 404)
    #     self.assertEqual(response.json.get('value'), None)

