from unittest import TestCase
from cilantro_ee.nodes.masternode.webserver import WebServer
from cilantro_ee.crypto.wallet import Wallet


class TestWS(TestCase):
    def setUp(self):
        self.server = WebServer(Wallet())

    def test_app(self):
        _, response = self.server.app.test_client.get('/ping')
        self.assertEqual(response.status, 200)

    def test_ping_api(self):
        _, response = self.server.app.test_client.get('/ping')
        self.assertEqual(response.status, 200)
        self.assertDictEqual(response.json, {
            'status': 'online'
        })

    def test_id_api(self):
        _, response = self.server.app.test_client.get('/id')
        self.assertEqual(response.json, {'verifying_key': self.server.wallet.verifying_key().hex()})


    def test_get_submission_methods(self):
        _, response = self.server.app.test_client.get('/contracts/submission/methods')

        method = 'submit_contract'
        kwargs = ['name', 'code', 'owner', 'constructor_args']

        methods = response.json.get('methods')

        self.assertEqual(len(methods), 1)

        test_method = methods[0]

        self.assertEqual(method, test_method.get('name'))
        self.assertListEqual(kwargs, test_method.get('arguments'))
        self.assertEqual(response.status, 200)

    def test_get_non_existent_contract_methods(self):
        _, response = self.server.app.test_client.get('/contracts/huuuuuuuuupluh/methods')

        self.assertEqual(response.status, 404)

        error_message = response.json.get('error')

        self.assertEqual(error_message, 'huuuuuuuuupluh does not exist')

    def test_contracts_api(self):
        _, response = self.server.app.test_client.get('/contracts/vkbook')
        pass

    def test_blocks_api(self):
        _, response = self.server.app.test_client.get('/latest_block')
        print(response.json)
        pass
