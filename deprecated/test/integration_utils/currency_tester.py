from cilantro_ee.core.logger.base import get_logger
from deprecated.test.dumpatron import Dumpatron
from deprecated.test import God
from deprecated.test.wallets import GENERAL_WALLETS
import random, asyncio
from collections import defaultdict


class CurrencyTester(Dumpatron):

    FETCH_BALANCES_TIMEOUT = 30
    ASSERT_BALANCES_TIMEOUT = 90
    SLEEP_BEFORE_ASSERTING = 12  # How long we should wait between sending transactions and asserting _new balances
    POLL_INTERVAL = 2

    MIN_AMOUNT = 1
    MAX_AMOUNT = 1000000

    def __init__(self, *args, wallets=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = get_logger("CurrencyTester")

        # For keeping track of wallet balances and asserting the correct amnt was deducted
        self.wallets = wallets or GENERAL_WALLETS
        self.all_vks = set([w[1] for w in self.wallets])
        self.deltas = defaultdict(int)
        self.init_balances = {}

    async def _start(self):
        await self.get_initial_balances()
        await self.send_test_currency_txs()
        self.log.test("Sleeping for {} seconds before checking assertions...".format(self.SLEEP_BEFORE_ASSERTING))
        await asyncio.sleep(self.SLEEP_BEFORE_ASSERTING)
        await self.assert_balances_updated()

    async def get_initial_balances(self):
        self.log.test("Getting initial balances for {} wallets...".format(len(self.wallets)))
        elapsed = 0
        while len(self.wallets) != len(self.init_balances):
            await asyncio.sleep(self.POLL_INTERVAL)
            elapsed += self.POLL_INTERVAL
            remaining_wallets = self.all_vks - set(self.init_balances.keys())

            if elapsed > self.FETCH_BALANCES_TIMEOUT:
                raise Exception("Exceeded timeout of {} trying to fetch initial wallet balances!\nWallets retreived: {}"
                                "\nWallets remaining: {}".format(self.FETCH_BALANCES_TIMEOUT, self.init_balances, remaining_wallets))

            balances = await God.get_balances(self.session, remaining_wallets)
            self.init_balances.update(balances)

        self.log.test("All initial wallet balances fetched!".format(self.init_balances))

    # TODO increase num_blocks to 4 once 1 works --davis
    async def send_test_currency_txs(self, num_blocks=4):
        assert len(self.init_balances) == len(self.wallets), "Init balances not equal to length of wallet"
        num = self.TX_PER_BLOCK * num_blocks
        self.log.test("Sending {} random test transactions...".format(num))

        txs = []
        for _ in range(num):
            sender, receiver = random.sample(self.wallets, 2)
            amount = random.randint(1, 10000)
            tx = God.create_currency_tx(sender, receiver, amount, self.STAMPS_AMOUNT)
            txs.append(tx)
            # self.deltas[sender[1]] -= (amount + self.STAMPS_AMOUNT)
            self.deltas[sender[1]] -= amount
            self.deltas[receiver[1]] += amount

        await God.async_send_txs(txs, self.session)
        self.log.test("Finish sending {} test transactions".format(num))

    async def assert_balances_updated(self):
        self.log.test("Starting assertion check for {} updated balances...".format(len(self.deltas)))

        elapsed = 0
        correct_wallets = set()
        latest_balances = {}  # Just for debugging info

        while len(correct_wallets) != len(self.deltas):
            remaining_vks = set(self.deltas.keys()) - correct_wallets

            if elapsed > self.ASSERT_BALANCES_TIMEOUT:
                raise Exception("Exceeded timeout of {} waiting for wallets to update!\nRemaining Wallets: {}\nLatest "
                                "Balances: {}\nDeltas: {}".format(self.ASSERT_BALANCES_TIMEOUT, remaining_vks,
                                                                  latest_balances, self.deltas))

            updated_balances = await God.get_balances(self.session, remaining_vks)
            for vk in updated_balances:
                expected_amount = max(0, self.init_balances[vk] + self.deltas[vk])
                actual_amount = updated_balances[vk]
                latest_balances[vk] = actual_amount
                if expected_amount == actual_amount:
                    correct_wallets.add(vk)
                else:
                    if elapsed >= self.ASSERT_BALANCES_TIMEOUT/2:
                        self.log.warning("Balance {} does not match expected balance {} for vk {}"
                                         .format(actual_amount, expected_amount, vk))

            await asyncio.sleep(self.POLL_INTERVAL)
            elapsed += self.POLL_INTERVAL

        self.log.success("Assertions for {} balance deltas passed!".format(len(self.deltas)))
