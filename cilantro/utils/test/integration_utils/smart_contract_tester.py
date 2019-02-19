from cilantro.logger.base import get_logger
from cilantro.utils.test.dumpatron import Dumpatron
from cilantro.utils.test.god import God
from cilantro.utils.test.wallets import GENERAL_WALLETS, STU
from cilantro.messages.transaction.publish import *
from cilantro.messages.transaction.container import TransactionContainer
from cilantro.messages.transaction.contract import ContractTransaction
import time, random, os
from collections import defaultdict


CONTRACT_FILENAME = 'stubucks.seneca'


class SmartContractTester(Dumpatron):

    ASSERT_CONTRACT_NOT_EXISTS_TIMEOUT = 60
    ASSERT_SUBMITTED_TIMEOUT = 30
    SLEEP_BEFORE_ASSERTING = 10  # How long we should wait between sending transactions and asserting new balances
    POLL_INTERVAL = 2

    CONTRACT_NAME = 'stubucks'

    def __init__(self, *args, wallets=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = get_logger("CurrencyTester")

        # For keeping track of wallet balances and asserting the correct amnt was deducted
        self.wallets = wallets or GENERAL_WALLETS
        self._all_vks = set([w[1] for w in self.wallets])
        self.deltas = defaultdict(int)
        self.init_balances = {}

        self.sk, self.vk = STU

    async def _start(self):
        self.assert_contract_does_not_exist()
        self.submit_contract()
        self.log.test("Sleeping for {} seconds before asserting contract was submitted...".format(self.SLEEP_BEFORE_ASSERTING))
        self.assert_contract_submitted()

    def assert_contract_does_not_exist(self):
        names = God.get_contract_names()
        if self.CONTRACT_NAME in names:
            raise Exception("Contract named '{}' already exists in Masternode's contracts {}".format(self.CONTRACT_NAME, names))

    def submit_contract(self):
        self.log.test("Submitting smart contract with owner vk {}".format(self.vk))
        code_file_path = os.path.dirname(__file__) + '/' + CONTRACT_FILENAME
        with open(code_file_path, 'r') as f:
            code_str = f.read()
        God.submit_contract(code_str, self.CONTRACT_NAME, self.sk, self.vk, stamps=self.STAMPS_AMOUNT)

    def assert_contract_submitted(self):
        self.log.test("Asserting that contract has been successfully submitted...")
        elapsed = 0
        while self.CONTRACT_NAME not in God.get_contract_names():
            self.log.info("Contract still not registered. Sleeping {} seconds".format(self.POLL_INTERVAL))
            time.sleep(self.POLL_INTERVAL)
            elapsed += self.POLL_INTERVAL
            if elapsed > self.ASSERT_SUBMITTED_TIMEOUT:
                raise Exception("Contract submission exceeded timeout of {}".format(self.ASSERT_SUBMITTED_TIMEOUT))

        self.log.test("Contract successfully submitted.")

    def submit_test_transaction(self):
        pass

    def assert_test_transaction_submitted(self):
        pass
