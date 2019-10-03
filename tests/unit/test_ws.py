from unittest import TestCase
from cilantro_ee.nodes.masternode.webserver import app, client
import json

class TestWS(TestCase):
    def test_app(self):
        _, response = app.test_client.get('/')
        self.assertEqual(response.status, 200)

    def test_ping_api(self):
        _, response = app.test_client.get('/ping')
        self.assertEqual(response.status,200)
        self.assertEqual(response.json, [True, 'Hello'])

    def test_id_api(self):
        _, response = app.test_client.get('/id')
        self.assertEqual(response.json, {'verifying_key': None})

    def test_epoch_api(self):
        _, response = app.test_client.get('/epoch')
        print(response.json)
        self.assertEqual(response.json,
                         {'epoch_hash': '0000000000000000000000000000000000000000000000000000000000000000',
                          'blocks_until_next_epoch': 1})

    def test_contracts_api(self):
        _, response = app.test_client.get('/contracts')
        pass

    def test_blocks_api(self):
        _, response = app.test_client.get('/latest_block')
        print(response.json)
        pass
