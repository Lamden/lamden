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

    def start(self):
        self.assert_contract_does_not_exist()
        self.submit_contract()
        self.log.test("Sleeping for {} seconds before asserting contract was submitted...".format(self.SLEEP_BEFORE_ASSERTING))
        self.assert_contract_submitted()

    def assert_contract_does_not_exist(self):
        elapsed = 0
        while self._check_contract_exists(self.CONTRACT_NAME) is not False:   # could be None so need 'is not False'
            elapsed += self.POLL_INTERVAL
            time.sleep(elapsed)
            if elapsed > self.ASSERT_CONTRACT_NOT_EXISTS_TIMEOUT:
                raise Exception("Exceeded timeout of {} asserting that contract does not exist yet".format(self.ASSERT_CONTRACT_NOT_EXISTS_TIMEOUT))

    def _check_contract_exists(self, contract_name) -> bool:
        res = God.get_contracts()
        self.log.critical(res)

    def submit_contract(self):
        self.log.test("Submitting smart contract with owner vk {}".format(self.vk))
        code_file_path = os.path.dirname(__file__) + '/' + CONTRACT_FILENAME
        with open(code_file_path, 'r') as f:
            code_str = f.read()

        print("submitting code str:\n{}".format(code_str))

    def assert_contract_submitted(self):
        pass

    def submit_test_transaction(self):
        pass

    def assert_test_transaction_submitted(self):
        pass

    # def get_initial_balances(self):
    #     # Blocks until Masternode is ready
    #     self.log.test("Getting initial balances for {} wallets...".format(len(self.wallets)))
    #     elapsed = 0
    #     while len(self.wallets) != len(self.init_balances):
    #         time.sleep(self.POLL_INTERVAL)
    #         elapsed += self.POLL_INTERVAL
    #         remaining_wallets = self._all_vks - set(self.init_balances.keys())
    #
    #         if elapsed > self.FETCH_BALANCES_TIMEOUT:
    #             raise Exception("Exceeded timeout of {} trying to fetch initial wallet balances!\nWallets retreived: {}"
    #                             "\nWallets remaining: {}".format(self.FETCH_BALANCES_TIMEOUT, self.init_balances, remaining_wallets))
    #
    #         for vk in remaining_wallets:
    #             balance = self._fetch_balance(vk)
    #             if balance is not None:
    #                 self.init_balances[vk] = balance
    #
    #     self.log.test("All initial wallet balances fetched!".format(self.init_balances))
    #
    # def send_test_currency_txs(self, num_blocks=8):
    #     assert len(self.init_balances) == len(self.wallets), "Init balances not equal to length of wallet"
    #     num = self.TX_PER_BLOCK * num_blocks
    #     self.log.test("Sending {} random test transactions...".format(num))
    #     for _ in range(num):
    #         sender, receiver = random.sample(self.wallets, 2)
    #         amount = random.randint(1, 10000)
    #
    #         tx = God.create_currency_tx(sender, receiver, amount, self.STAMPS_AMOUNT)
    #         reply = God.send_tx(tx)
    #
    #         if reply is not None and reply.status_code == 200:
    #             self.deltas[sender[1]] -= (amount + self.STAMPS_AMOUNT)
    #             self.deltas[receiver[1]] += amount
    #         else:
    #             raise Exception("Got non 200 status code from sending tx to masternode")
    #     self.log.test("Finish sending {} test transactions".format(num))
    #
    # def assert_balances_updated(self):
    #     self.log.test("Starting assertion check for {} updated balances...".format(len(self.deltas)))
    #
    #     elapsed = 0
    #     correct_wallets = set()
    #     latest_balances = {}  # Just for debugging info
    #
    #     while len(correct_wallets) != len(self.deltas):
    #         time.sleep(self.POLL_INTERVAL)
    #         elapsed += self.POLL_INTERVAL
    #         remaining_vks = set(self.deltas.keys()) - correct_wallets
    #
    #         if elapsed > self.ASSERT_BALANCES_TIMEOUT:
    #             raise Exception("Exceeded timeout of {} waiting for wallets to update!\nRemaining Wallets: {}\nLatest "
    #                             "Balances: {}\nDeltas: {}".format(self.ASSERT_BALANCES_TIMEOUT, remaining_vks,
    #                                                               latest_balances, self.deltas))
    #
    #         for vk in remaining_vks:
    #             expected_amount = max(0, self.init_balances[vk] + self.deltas[vk])
    #             actual_amount = self._fetch_balance(vk)  # TODO get VKs from ALL masternodes; make sure they same
    #             latest_balances[vk] = actual_amount
    #             if expected_amount == actual_amount:
    #                 correct_wallets.add(vk)
    #             else:
    #                 self.log.warning("Balance {} does not match expected balance {} for vk {}"
    #                                  .format(actual_amount, expected_amount, vk))
    #
    #     self.log.success("Assertions for {} balance deltas passed!".format(len(self.deltas)))



    # def submit_contract(code, name, sk=SK_STU, vk=VK_STU, stamps=10 ** 6):
    #     tx = PublishTransaction.create(contract_code=code,
    #                                    contract_name=name,
    #                                    sender_sk=sk,
    #                                    nonce=vk + secrets.token_hex(32),
    #                                    stamps_supplied=stamps)
    #
    #     container = TransactionContainer.create(tx)
    #     data = container.serialize()
    #
    #     r = requests.post(SERVER, data=data, verify=False)
    #     print(r.text)
    #
    # def transact(contract, function, sk=SK_STU, vk=VK_STU, stamps=10 ** 6, **kwargs):
    #     tx = ContractTransaction.create(contract_name=contract,
    #                                     func_name=function,
    #                                     sender_sk=sk,
    #                                     nonce=vk + secrets.token_hex(32),
    #                                     stamps_supplied=stamps,
    #                                     **kwargs)
    #
    #     container = TransactionContainer.create(tx)
    #     data = container.serialize()
    #
    #     r = requests.post(SERVER, data=data, verify=False)
    #     print(r.text)
    #
    # def give(to='01a74f520cc0f9382e0504b55cea042957f3d5252499a2c0ab62a6b02b6c494a', amount=10 ** 6):
    #     transact(contract='currency', function='transfer', to=to, amount=amount)