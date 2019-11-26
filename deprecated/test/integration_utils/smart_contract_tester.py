from deprecated.test.dumpatron import Dumpatron
from deprecated.test import God
from deprecated.test.wallets import *
import time, os

CONTRACT_FILENAME = 'stubucks.sen.py'


class SmartContractTester(Dumpatron):

    ASSERT_CONTRACT_NOT_EXISTS_TIMEOUT = 6
    ASSERT_TX_TIMEOUT = 40
    ASSERT_SUBMITTED_TIMEOUT = 40
    ASSERT_SEEDED_TIMEOUT = 40
    SLEEP_BEFORE_ASSERTING = 10  # How long we should wait between sending transactions and asserting _new balances
    POLL_INTERVAL = 2

    TEST = 10

    CONTRACT_NAME = 'stubucks'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = get_logger("SmartContractTester")

        self.sk1, self.vk1 = STU
        self.sk2, self.vk2 = DAVIS

    async def _start(self):
        self.assert_contract_does_not_exist()
        self.submit_contract()
        self.log.test("Sleeping for {} seconds before asserting contract was submitted...".format(self.SLEEP_BEFORE_ASSERTING))
        time.sleep(self.SLEEP_BEFORE_ASSERTING)
        self.assert_contract_submitted()
        self.assert_contract_seeded()

        self.submit_balance_tx()
        self.log.test("Sleeping for {} seconds before asserting balances tx work submitted...".format(self.SLEEP_BEFORE_ASSERTING))
        time.sleep(self.SLEEP_BEFORE_ASSERTING)
        self.assert_balance_tx_worked()
        self.submit_custodial_tx()
        self.log.test("Sleeping for {} seconds before asserting custodial tx work submitted...".format(self.SLEEP_BEFORE_ASSERTING))
        time.sleep(self.SLEEP_BEFORE_ASSERTING)
        self.assert_custodial_tx_worked()

    def assert_contract_does_not_exist(self):
        names = God.get_contract_names()
        if self.CONTRACT_NAME in names:
            raise Exception("Contract named '{}' already exists in Masternode's contracts {}".format(self.CONTRACT_NAME, names))

    def submit_contract(self):
        self.log.test("Submitting smart contract with owner vk {}".format(self.vk1))
        code_file_path = os.path.dirname(__file__) + '/' + CONTRACT_FILENAME
        with open(code_file_path, 'r') as f:
            code_str = f.read()
        God.submit_contract(code_str, self.CONTRACT_NAME, self.sk1, self.vk1, stamps=self.STAMPS_AMOUNT)

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

    def assert_contract_seeded(self):
        self.log.test("Asserting that contract has been successfully seeded...")
        elapsed = 0
        while not self._check_value('balances', self.vk1, 1000000):
            time.sleep(self.POLL_INTERVAL)
            elapsed += self.POLL_INTERVAL
            if elapsed > self.ASSERT_SEEDED_TIMEOUT:
                raise Exception("Contract seeding exceeded timeout of {}".format(self.ASSERT_SEEDED_TIMEOUT))

    def submit_balance_tx(self):
        tx = God.create_contract_tx(self.sk1, self.CONTRACT_NAME, 'transfer', self.STAMPS_AMOUNT, to=self.vk2,
                                    amount=1337)
        self.log.test("Sending balance transaction {}".format(tx))
        God.send_tx(tx)

    def submit_custodial_tx(self):
        tx = God.create_contract_tx(self.sk2, self.CONTRACT_NAME, 'add_to_custodial', self.STAMPS_AMOUNT, to=self.vk1,
                                    amount=337)
        self.log.test("Sending custodial transaction {}".format(tx))
        God.send_tx(tx)

    def _get_sc_data(self, table, key):
        return God.get_from_mn_api('contracts/{}/{}/{}'.format(self.CONTRACT_NAME, table, key))

    def _check_value(self, table, key, expected_value, assume_int=True) -> bool:
        full_key = "{}/{}/{}".format(self.CONTRACT_NAME, table, key)
        actual = self._get_sc_data(table, key)

        if actual is None:
            actual = '<fetch returned None>'
        else:
            if assume_int:
                assert 'value' in actual, "Return JSON for key {} expected to have key 'value', but instead {}"\
                                          .format(full_key, actual)
                if actual['value'] == 'null':
                    actual = '<fetch returned None>'
                else:
                    actual = int(actual['value'])

        if actual != expected_value:
            self.log.warning("Key {} expected to have value {} but actually has value {}"
                             .format(full_key, expected_value, actual))
            return False
        return True

    def assert_balance_tx_worked(self):
        def _check_sender_deducted():
            return self._check_value('balances', self.vk1, 1000000 - 1337)

        def _check_recv_funded():
            return self._check_value('balances', self.vk2, 1337)

        elapsed = 0
        self.log.test("Checking to make sure stubucks were sent...")
        while not (_check_sender_deducted() and _check_recv_funded()):
            elapsed += self.POLL_INTERVAL
            time.sleep(self.POLL_INTERVAL)
            if elapsed > self.ASSERT_TX_TIMEOUT:
                raise Exception("Exceeded timeout of {} waiting for balance assertions to pass"
                                .format(self.ASSERT_TX_TIMEOUT))

    def assert_custodial_tx_worked(self):
        def _check_sender_deducted():
            return self._check_value('balances', self.vk2, 1337 - 337)

        def _check_recv_funded():
            return self._check_value('custodials', self.vk1, 337)

        elapsed = 0
        self.log.test("Checking to make sure custodials were sent...")
        while not (_check_sender_deducted() and _check_recv_funded()):
            elapsed += self.POLL_INTERVAL
            time.sleep(self.POLL_INTERVAL)
            if elapsed > self.ASSERT_TX_TIMEOUT:
                raise Exception("Exceeded timeout of {} waiting for custodial assertions to pass"
                                .format(self.ASSERT_TX_TIMEOUT))


