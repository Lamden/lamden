from cilantro.messages.transaction.container import TransactionContainer
from cilantro.messages.transaction.contract import *
from cilantro.messages.signals.kill_signal import KillSignal

from cilantro.logger import get_logger
from cilantro.utils.test.utils import *
from cilantro.utils.test.wallets import ALL_WALLETS
from cilantro.utils.test.node_runner import *
import os, requests, time, random, asyncio

from unittest.mock import MagicMock
from cilantro.protocol import wallet
from cilantro.constants.system_config import *


class God:
    # For MP tests  TODO i dont think we need this  --davis
    node_map = None
    testers = []

    log = get_logger("GOD")

    mn_urls = get_mn_urls()
    multi_master = type(mn_urls) is list  # If True, outgoing transactions will be round-robined to all masternodes
    _current_mn_idx = 0

    def __init__(self):
        raise NotImplementedError("Use only class method on God")

    @staticmethod
    def run_mn(*args, return_fn=True, **kwargs):
        if return_fn:
            return wrap_func(run_mn, *args, **kwargs)
        else:
            run_mn(*args, **kwargs)

    @staticmethod
    def run_witness(*args, return_fn=True, **kwargs):
        if return_fn:
            return wrap_func(run_witness, *args, **kwargs)
        else:
            run_witness(*args, **kwargs)

    @staticmethod
    def run_delegate(*args, return_fn=True, **kwargs):
        if return_fn:
            return wrap_func(run_delegate, *args, **kwargs)
        else:
            run_delegate(*args, **kwargs)

    @staticmethod
    def dump_it(*args, return_fn=True, **kwargs):
        God.mn_urls = get_mn_urls()  # Reset MN URLS
        if return_fn:
            return wrap_func(dump_it, *args, **kwargs)
        else:
            dump_it(*args, **kwargs)

    @staticmethod
    def pump_it(*args, return_fn=True, **kwargs):
        God.mn_urls = get_mn_urls()  # Reset MN URLS
        if return_fn:
            return wrap_func(pump_it, *args, **kwargs)
        else:
            pump_it(*args, **kwargs)

    @classmethod
    def teardown_all(cls, masternode_url):
        raise NotImplementedError("This is not implemented!")
        # masternode_url += '/teardown-network'
        # cls.log.important("Sending teardown notification to Masternode at url {}".format(masternode_url))
        # r = requests.post(masternode_url, data=KillSignal.create().serialize())

    @classmethod
    def _default_gen_func(cls):
        return cls.random_contract_tx

    @classmethod
    def set_mn_url(cls, ip='localhost', port=8080):
        raise NotImplementedError("This is deprecated!!!")

    @classmethod
    def create_currency_tx(cls, sender: tuple, receiver: tuple, amount: int, nonce=None):
        if type(receiver) is tuple:
            receiver = receiver[1]

        return ContractTransactionBuilder.create_currency_tx(sender[0], receiver, amount, nonce=nonce)

    @classmethod
    def send_currency_contract(cls, sender: tuple, receiver: tuple, amount:int):
        tx = cls.create_currency_tx(sender, receiver, amount)
        cls.send_tx(tx)

    @classmethod
    def send_tx(cls, tx: TransactionBase):
        mn_url = cls._get_mn_url()
        try:
            r = requests.post(mn_url, data=TransactionContainer.create(tx).serialize())
            cls.log.spam("POST request to MN at URL {} has status code: {}".format(mn_url, r.status_code))
            return r
        except Exception as e:
            cls.log.warning("Error attempt to send transaction to Masternode at URL {}\nerror={}".format(mn_url, e))
            return None

    @classmethod
    def _pump_it(cls, rate: int, gen_func=None, use_poisson=True, sleep_sometimes=False, active_bounds=(120, 240),
                 sleep_bounds=(20, 60), pump_wait=0):
        """
        Pump random transactions from random users to Masternode's REST endpoint at an average rate of 'rate'
        transactions per second. This func blocks.
        """
        if pump_wait > 0:
            cls.log.important("Pumper sleeping {} seconds before starting...".format(pump_wait))
            time.sleep(pump_wait)

        if not gen_func:
            gen_func = cls._default_gen_func()

        if use_poisson:
            from scipy.stats import poisson, expon
            rvs_func = lambda: expon.rvs(rate)/rate - 1
        else:
            rvs_func = lambda: 1/rate

        assert callable(gen_func), "Expected a callable for 'gen_func' but got {}".format(gen_func)

        cls.log.important3("Starting to pump transactions at an average of {} transactions per second".format(rate))
        cls.log.test("Using generator func {}, use_possion={}, sleep_sometimes={}, active_bounds={}, sleep_bounds={}"
                     .format(gen_func, use_poisson, sleep_sometimes, active_bounds, sleep_bounds))

        time_since_last_sleep = 0
        next_sleep = random.randint(active_bounds[0], active_bounds[1])
        if sleep_sometimes:
            cls.log.important3("Next sleep will be in {}s".format(next_sleep))

        while True:
            wait = rvs_func()
            # cls.log.spam("Sending next transaction in {} seconds".format(wait))
            time.sleep(wait)
            time_since_last_sleep += wait

            tx = gen_func()
            # cls.log.spam("sending transaction {}".format(tx))
            cls.send_tx(tx)

            if sleep_sometimes and time_since_last_sleep >= next_sleep:
                sleep_time = random.randint(sleep_bounds[0], sleep_bounds[1])
                cls.log.important3("Sleeping for {}s before pumping more...")
                time.sleep(sleep_time)

                time_since_last_sleep = 0
                next_sleep = random.randint(active_bounds[0], active_bounds[1])
                cls.log.important3("Done sleeping. Continuing the pump, and triggering next sleep in {}s".format(next_sleep))

    @classmethod
    def _dump_it(cls, volume: int, delay: int=0, gen_func=None):
        """ Dump it fast. """
        assert volume > 0, "You must dump at least 1 transaction silly"

        if not gen_func:
            gen_func = cls._default_gen_func()

        gen_start_time = time.time()
        cls.log.important2("Generating {} transactions to dump...".format(volume))
        txs = [gen_func() for _ in range(volume)]
        cls.log.important2("Done generating transactions.")

        delay -= int(time.time() - gen_start_time)
        countdown(delay, "Waiting for an additional {} seconds before dumping...", cls.log, status_update_freq=8)

        start = time.time()
        cls.log.important2("Dumping {} transactions...".format(len(txs)))
        for tx in txs:
            cls.send_tx(tx)
        cls.log.important2("Done dumping {} transactions in {} seconds".format(len(txs), round(time.time() - start, 3)))

    @classmethod
    def request_nonce(cls, vk):
        mn_url = cls._get_mn_url() + '/nonce'
        try:
            r = requests.get(mn_url, json={'verifyingKey': vk})
            cls.log.debugv("GET request to MN at URL {} has status code: {}".format(mn_url, r.status_code))
            return r.json()

        except Exception as e:
            cls.log.warning("Error attempt to send transaction to Masternode at URL {}\nerror={}".format(mn_url, e))
            return 'error: {}'.format(e)

    @classmethod
    def random_contract_tx(cls):
        sender, receiver = random.sample(ALL_WALLETS, 2)
        amount = random.randint(1, 100)

        return cls.create_currency_tx(sender=sender, receiver=receiver, amount=amount)

    @classmethod
    def _get_mn_url(cls):
        if cls.multi_master:
            mn_url = cls.mn_urls[cls._current_mn_idx]
            cls._current_mn_idx = (cls._current_mn_idx + 1) % len(cls.mn_urls)
            cls.log.debug("Multi-master detected. Using Masternode at IP {}".format(mn_url))
        else:
            mn_url = cls.mn_urls[0]
        return mn_url

