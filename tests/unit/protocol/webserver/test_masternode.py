import unittest, sys, asyncio
from unittest import TestCase
from cilantro.nodes.masternode.webserver import start_webserver
from cilantro.constants.testnet import TESTNET_MASTERNODES
from cilantro.logger.base import get_logger
from multiprocessing import Process
from multiprocessing import Queue
import requests
from cilantro.protocol.webserver.sanic import SanicSingleton
from cilantro import tools
from cilantro.constants.masternode import WEB_SERVER_PORT

server_url = 'localhost:{}'.format(WEB_SERVER_PORT)
log = get_logger(__name__)

class SanicServer:

    def __init__(self, sk):
        self.sk = sk

    def start(self):
        self.p = Process(target=start_webserver, args=(Queue(),))
        self.p.start()

    def stop(self):
        self.p.terminate()

class TestMasterNodeWebserver(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server = SanicServer(TESTNET_MASTERNODES[0]['sk'])
        cls.server.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def setUp(self):
        SanicSingleton.interface.r.flushdb()
        for contract in ['currency']:
            with open('{}.sen.py'.format(contract)) as f:
                code_str = f.read()
                setattr(self, contract, code_str)
                SanicSingleton.interface.publish_code_str(contract, 'lorde', code_str)

    def test_get_contract_meta(self):
        r = tools.get_contract_meta('currency', server_url)
        self.assertEqual(self.currency, r['code_str'])
        self.assertEqual(set([
            'balances',
            'allowed',
            'market'
        ]), set(r['datatypes'].keys()))
        self.assertEqual(set([
            'submit_stamps',
            'balance_of',
            'transfer',
            'approve',
            'transfer_from',
            'allowance',
            'mint'
        ]), set(r['exports']))

    def test_get_contract_state(self):
        r = tools.get_contract_state('currency', 'balances', 'lorde', server_url)
        self.assertEqual(r, 10000)

#     def submit_poll_contract(self):
#         TransactionContainer.create()
#         return requests.post('http://localhost:8080/submit-contract', json={
#             'contract_name': 'voting',
#             'author': 'lorde',
#             'code_str': '''
# from seneca.libs.datatypes import hmap
#
# poll = hmap('poll', str, int)
#
# @export
# def vote(name):
#     poll[name] += 1
#
# @export
# def voter_count(name):
#     return poll[name]
#             '''
#         }).json()
#
#     def vote(self, sender, name):
#         return requests.post('http://localhost:8080/run-contract', json={
#             'contract_call': 'voting.vote',
#             'sender': sender,
#             'stamps': 2000,
#             'parameters': {'name': name}
#         }).json()
#
#     def voter_count(self, sender, name):
#         return requests.post('http://localhost:8080/run-contract', json={
#             'contract_call': 'voting.voter_count',
#             'sender': sender,
#             'stamps': 2000,
#             'parameters': {'name': name}
#         }).json()
#
#     def test_submit_contract(self):
#         r = self.submit_poll_contract()
#         self.assertEqual(r, {"status":"success","contract_name":"voting"})
#
#     def test_run_contract(self):
#         self.submit_poll_contract()
#         r = self.vote('john', 'john')
#         self.assertEqual(r['output'], None)
#         self.assertEqual(r['status'], 'success')
#
#     def test_get_state(self):
#         self.submit_poll_contract()
#         self.vote('john', 'john')
#         r = self.voter_count('peter', 'john')
#         self.assertEqual(r['output'], 1)
#         self.assertEqual(r['status'], 'success')

if __name__ == '__main__':
    unittest.main()
