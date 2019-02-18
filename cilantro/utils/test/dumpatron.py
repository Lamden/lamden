from cilantro.logger.base import get_logger
from cilantro.utils.test.god import God
from cilantro.constants.system_config import *
from cilantro.utils.test.wallets import ALL_WALLETS
import sys, os, glob
from itertools import combinations
import random, requests, time
from collections import defaultdict, Or


SSL_ENABLED = False  # TODO make this infered instead of a hard coded flag
CURRENCY_CONTRACT_NAME = 'currency'
IP_FILE_PREFIX = 'ip_masternode'


class Dumpatron:

    TX_PER_BLOCK = TRANSACTIONS_PER_SUB_BLOCK * NUM_SB_PER_BLOCK * NUM_BLOCKS

    def __init__(self, env_path):
        if env_path[-1] != '/':
            env_path += '/'
        assert os.path.exists(env_path), "No env dir found at path {}".format(env_path)
        assert os.path.exists(env_path + '.cache'), "No .cache dir found at path {}.cache".format(env_path)
        self.log = get_logger("Dumpatron")

        self.env_path = env_path
        self.mn_ip_dict = self._extract_mn_ips()
        self.mn_url_list = self._get_mn_urls_from_ips(self.mn_ip_dict)

        God.mn_urls = self.mn_url_list
        God.multi_master = True

    def _extract_mn_ips(self) -> dict:
        ips = {}
        pattern = "{}.cache/{}*".format(self.env_path, IP_FILE_PREFIX)
        mn_files = glob.glob(pattern)
        assert len(mn_files) > 0, "No masternode ip config files found matching glob pattern {} (did colin change the" \
                                  " way IPs are cached?)".format(pattern)

        for mn_file in mn_files:
            with open(mn_file, 'r') as f:
                mn_idx = mn_file[len(IP_FILE_PREFIX):]
                ips[mn_file[-1]] = f.read()
        return ips

    # TODO factor this out into its own function/module so it can be used in God as well
    def _get_mn_urls_from_ips(self, ips: dict) -> list:
        urls = []
        for ip in ips.values():
            if SSL_ENABLED:
                urls.append("https://{}".format(ip))
            else:
                urls.append("http://{}:8080".format(ip))
        return urls

    def dump(self, volume=1):
        God._dump_it(volume=volume)

    def start_interactive_dump(self):
        self.log.info("Starting the dump....")
        while True:
            user_input = input("Enter an integer representing the # of transactions to dump, or 'x' to quit. "
                               "Press enter to dump 1 blocks\n")

            if user_input.lower() == 'x':
                self.log.important("Termination input detected. Breaking")
                break

            vol = int(user_input) if user_input.isdigit() else self.TX_PER_BLOCK
            self.log.important3("Dumping {} transactions!".format(vol))
            God._dump_it(volume=vol)


class DumpatronTester(Dumpatron):

    FETCH_BALANCES_TIMEOUT = 240
    CHECK_BALANCES_TIMEOUT = 20
    POLL_INTERVAL = 2
    STAMPS_AMOUNT = 10000

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = get_logger("DumpatronTester")

        # For keeping track of wallet balances and asserting the correct amnt was deducted
        self.wallets = ALL_WALLETS
        self._all_vks = set([w[1] for w in self.wallets])
        self.deltas = defaultdict(int)
        self.init_balances = {}

    def start(self):
        self.get_initial_balances()
        self.send_test_currency_txs()
        self.assert_balances_updated()

    def get_initial_balances(self):
        # Blocks until Masternode is ready

        self.log.info("Getting initial wallet balances...")
        elapsed = 0
        while len(self.wallets) != len(self.init_balances):
            time.sleep(self.POLL_INTERVAL)
            elapsed += self.POLL_INTERVAL
            remaining_wallets = self._all_vks - set(self.init_balances.keys())

            if elapsed > self.FETCH_BALANCES_TIMEOUT:
                raise Exception("Exceeded timeout of {} trying to fetch initial wallet balances!\nWallets retreived: {}"
                                "\nWallets remaining: {}".format(self.FETCH_BALANCES_TIMEOUT, self.init_balances, remaining_wallets))

            for vk in remaining_wallets:
                balance = self._fetch_balance(self.wallets[0][1], 0)
                if balance is not None:
                    self.init_balances[vk] = balance

        self.log.info("All initial wallet balances fetched!\nInitial balances: {}".format(self.init_balances))

    def _fetch_balance(self, vk, mn_idx) -> int or None:
        mn_url = self.mn_url_list[mn_idx]
        self.log.spam("Fetching balance for vk {} from mn with idx {} at url {}".format(vk, mn_idx, mn_url))

        req_url = "{}/contracts/{}/balances/{}".format(mn_url, CURRENCY_CONTRACT_NAME, vk)
        req = requests.get(req_url)

        if req.status_code == 200:
            ret_json = req.json()
            assert 'value' in ret_json, "Expected key 'value' to be in reply json {}".format(ret_json)
            return int(ret_json['value'])
        else:
            self.log.spam("Got response {} with status code {} and json {}".format(req, req.status_code, req.json()))
            return None

    def send_test_currency_txs(self, num=4):
        assert len(self.init_balances) == len(self.wallets), "Init balances not equal to length of wallet"
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

    def assert_balances_updated(self):
        self.log.notice("Starting assertion check for updated balances...")

        elapsed = 0
        correct_wallets = set()
        latest_balances = {}  # Just for debugging

        self.log.important2(self.deltas)

        while len(correct_wallets) != len(self.deltas):
            time.sleep(self.POLL_INTERVAL)
            elapsed += self.POLL_INTERVAL
            remaining_vks = set(self.deltas.keys()) - correct_wallets

            if elapsed > self.CHECK_BALANCES_TIMEOUT:
                raise Exception("Exceeded timeout of {} waiting for wallets to update!\nRemaining Wallets: {}\nLatest "
                                "Balances: {}\nDeltas: {}".format(self.CHECK_BALANCES_TIMEOUT, remaining_vks,
                                                                  latest_balances, self.deltas))

            for vk in remaining_vks:
                expected_amount = self.init_balances[vk] + self.deltas[vk]
                actual_amount = self._fetch_balance(vk, 0)  # TODO get VKs from ALL masternodes; make sure they same
                latest_balances[vk] = actual_amount
                if expected_amount == actual_amount:
                    correct_wallets.add(vk)
                else:
                    self.log.warning("Balance {} does not match expected balance {} for vk {}"
                                     .format(actual_amount, expected_amount, vk))



