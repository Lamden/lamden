import unittest, sys, asyncio
from unittest import TestCase
from cilantro.protocol.webserver.masternode import start_webserver
from cilantro.constants.testnet import TESTNET_MASTERNODES
from cilantro.logger.base import get_logger
from multiprocessing import Process
from multiprocessing import Queue
import requests

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
        pass

    def test_submit_contract(self):
        r = requests.post('http://localhost:8080/submit-contract', data = {
            'contract_name': 'wow',
            'author': 'bruh',
            'code_str': '''
@export
def hello():
    return 'world'
            '''
        })
        log.critical(r)

if __name__ == '__main__':
    unittest.main()
