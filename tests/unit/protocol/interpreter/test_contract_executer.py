from seneca.engine.client import SenecaClient
from cilantro.messages.transaction.contract import ContractTransaction, ContractTransactionBuilder
from cilantro.constants.testnet import TESTNET_DELEGATES
import unittest
from unittest import TestCase

sk = TESTNET_DELEGATES[0]['sk']

class TestContractExecuter(TestCase):
    def setUp(self):
        sbb_idx = 0
        num_sub = 2
        self.client = SenecaClient(sbb_idx, num_sub, concurrent_mode=False)
        self.client.reset_db(self.client.master_db)
        self.contract = ContractTransactionBuilder.create_contract_tx(
            sender_sk=sk,
            code_str='''
print('In Smart Contract: Hello World!')
            ''', contract_name='sample')

    def test_submit(self):
        self.client.submit_contract(self.contract)

    def test_run(self):
        self.client.submit_contract(self.contract)
        self.client.run_contract(self.contract)

if __name__ == '__main__':
    unittest.main()
