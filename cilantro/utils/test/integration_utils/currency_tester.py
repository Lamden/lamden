from cilantro.logger.base import get_logger
from cilantro.utils.test.dumpatron import Dumpatron
from cilantro.utils.test.god import God
from cilantro.utils.test.wallets import GENERAL_WALLETS
import time, random
from collections import defaultdict


class CurrencyTester(Dumpatron):

    FETCH_BALANCES_TIMEOUT = 240
    ASSERT_BALANCES_TIMEOUT = 60
    SLEEP_BEFORE_ASSERTING = 10  # How long we should wait between sending transactions and asserting new balances
    POLL_INTERVAL = 2

    MIN_AMOUNT = 1
    MAX_AMOUNT = 1000000

    def __init__(self, *args, wallets=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = get_logger("CurrencyTester")

        # For keeping track of wallet balances and asserting the correct amnt was deducted
        self.wallets = wallets or GENERAL_WALLETS
        self._all_vks = set([w[1] for w in self.wallets])
        self.deltas = defaultdict(int)
        self.init_balances = {}

    def start(self):
        self.get_initial_balances()
        self.send_test_currency_txs()
        self.log.test("Sleeping for {} seconds before checking assertions...".format(self.SLEEP_BEFORE_ASSERTING))
        time.sleep(self.SLEEP_BEFORE_ASSERTING)
        self.assert_balances_updated()

    def get_initial_balances(self):
        # Blocks until Masternode is ready
        self.log.test("Getting initial balances for {} wallets...".format(len(self.wallets)))
        elapsed = 0
        while len(self.wallets) != len(self.init_balances):
            time.sleep(self.POLL_INTERVAL)
            elapsed += self.POLL_INTERVAL
            remaining_wallets = self._all_vks - set(self.init_balances.keys())

            if elapsed > self.FETCH_BALANCES_TIMEOUT:
                raise Exception("Exceeded timeout of {} trying to fetch initial wallet balances!\nWallets retreived: {}"
                                "\nWallets remaining: {}".format(self.FETCH_BALANCES_TIMEOUT, self.init_balances, remaining_wallets))

            for vk in remaining_wallets:
                balance = self._fetch_balance(vk)
                if balance is not None:
                    self.init_balances[vk] = balance

        self.log.test("All initial wallet balances fetched!".format(self.init_balances))

    def send_test_currency_txs(self, num_blocks=8):
        assert len(self.init_balances) == len(self.wallets), "Init balances not equal to length of wallet"
        num = self.TX_PER_BLOCK * num_blocks
        self.log.test("Sending {} random test transactions...".format(num))
        for _ in range(num):
            sender, receiver = random.sample(self.wallets, 2)
            amount = random.randint(1, 10000)

            tx = God.create_currency_tx(sender, receiver, amount, self.STAMPS_AMOUNT)
            reply = God.send_tx(tx)

            if reply is not None and reply.status_code == 200:
                self.deltas[sender[1]] -= (amount + self.STAMPS_AMOUNT)
                self.deltas[receiver[1]] += amount
            else:
                raise Exception("Got non 200 status code from sending tx to masternode")
        self.log.test("Finish sending {} test transactions".format(num))

    def assert_balances_updated(self):
        self.log.test("Starting assertion check for {} updated balances...".format(len(self.deltas)))

        elapsed = 0
        correct_wallets = set()
        latest_balances = {}  # Just for debugging info

        while len(correct_wallets) != len(self.deltas):
            time.sleep(self.POLL_INTERVAL)
            elapsed += self.POLL_INTERVAL
            remaining_vks = set(self.deltas.keys()) - correct_wallets

            if elapsed > self.ASSERT_BALANCES_TIMEOUT:
                raise Exception("Exceeded timeout of {} waiting for wallets to update!\nRemaining Wallets: {}\nLatest "
                                "Balances: {}\nDeltas: {}".format(self.ASSERT_BALANCES_TIMEOUT, remaining_vks,
                                                                  latest_balances, self.deltas))

            for vk in remaining_vks:
                expected_amount = max(0, self.init_balances[vk] + self.deltas[vk])
                actual_amount = self._fetch_balance(vk)  # TODO get VKs from ALL masternodes; make sure they same
                latest_balances[vk] = actual_amount
                if expected_amount == actual_amount:
                    correct_wallets.add(vk)
                else:
                    self.log.warning("Balance {} does not match expected balance {} for vk {}"
                                     .format(actual_amount, expected_amount, vk))

        self.log.success("Assertions for {} balance deltas passed!".format(len(self.deltas)))