from cilantro.logger.base import get_logger
from cilantro.utils.test.god import God
from cilantro.constants.system_config import *
from cilantro.utils.test.wallets import *
import sys, os, glob
from itertools import combinations
import random, requests, time


SSL_ENABLED = False  # TODO make this infered instead of a hard coded flag
CURRENCY_CONTRACT_NAME = 'currency'


class Dumpatron:

    TX_PER_BLOCK = TRANSACTIONS_PER_SUB_BLOCK * NUM_SB_PER_BLOCK * NUM_BLOCKS

    def __init__(self, env_path):
        assert os.path.exists(env_path), "No env dir found at path {}".format(env_path)
        assert os.path.exists(env_path + '.cache'), "No .cache dir found at path {}.cache".format(env_path)
        self.log = get_logger("Dumpatron")

        self.env_path = env_path
        self.mn_ip_dict = self._extract_mn_ips()
        self.mn_url_list = self._get_mn_urls_from_ips(self.mn_ip_dict)

        God.mn_urls = self.mn_url_list
        God.multi_master = True

    def _extract_mn_ips(self) -> dict:
        mn_files = glob.glob("{}.cache/ip_masternode*".format(self.env_path))
        ips = {}
        for mn_file in mn_files:
            with open(mn_file, 'r') as f:
                ips[mn_file[-1]] = f.read()
        return ips

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = get_logger("DumpatronTester")

        # For keeping track of wallet balances and asserting the correct amnt was deducted
        self.wallets = ALL_WALLETS
        self.deltas = {}
        self.init_balances = {}

        self.get_initial_balances()

    def get_initial_balances(self):
        # Blocks until Masternode is ready
        self.log.info("Getting wallet balances...")

        while True:
            self._fetch_balance(self.wallets[0][1], 0)
            time.sleep(2)

    def _fetch_balance(self, vk, mn_idx) -> int:
        mn_url = self.mn_url_list[mn_idx]
        log.debugv("Fetching balance for vk {} from mn with idx {} at url {}".format(vk, mn_idx, mn_url))

        req_url = "{}/contracts/{}/balances/{}".format(mn_url, CURRENCY_CONTRACT_NAME, vk)
        req = requests.get(req_url)

        self.log.info("Got response {} with status code {} and json {}".format(req, req.status_code, req.json()))


    def send_test_txs(self, num=10):

        tx1 = God.create_currency_tx(sender=COLIN, receiver=DAVIS, amount=1234, stamps=10000)