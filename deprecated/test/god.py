from cilantro_ee.messages.transaction.publish import *
from cilantro_ee.messages.transaction.contract import *

from deprecated.test.utils import *
from deprecated.test.wallets import ALL_WALLETS
import requests, time, random, asyncio, secrets
from typing import List
from decimal import Decimal


CURRENCY_CONTRACT_NAME = 'currency'



class God:
    # For MP tests  TODO i dont think we need this  --davis
    node_map = None
    testers = []

    log = get_logger("GOD")

    mn_urls = []
    _current_mn_idx = 0

    def __init__(self):
        raise NotImplementedError("Use only class method on God")

    @classmethod
    def _default_gen_func(cls):
        return cls.random_contract_tx

    @classmethod
    def create_currency_tx(cls, sender: tuple, receiver: tuple, amount: int, stamps=10000, nonce=None):
        if type(receiver) is tuple:
            receiver = receiver[1]

        return ContractTransactionBuilder.create_currency_tx(sender[0], receiver, amount, stamps=stamps, nonce=nonce)

    @classmethod
    def create_contract_tx(cls, sender_sk: str, contract_name: str, func_name: str, stamps=10000,
                           nonce=None, **kwargs) -> ContractTransaction:
        if nonce is None:
            nonce = wallet.get_vk(sender_sk) + ':' + 'A'*64
        return ContractTransaction.create(sender_sk, stamps, contract_name, func_name, nonce, kwargs)

    @classmethod
    def send_currency_contract(cls, sender: tuple, receiver: tuple, amount: int):
        tx = cls.create_currency_tx(sender, receiver, amount)
        return cls.send_tx(tx)

    @classmethod
    def send_tx(cls, tx):
        assert len(cls.mn_urls) > 0, "mn_urls must be set to send_tx! "
        mn_url = cls._get_mn_url()
        data = TransactionContainer.create(tx).serialize()
        try:
            r = requests.post(mn_url, data=data, verify=False)
            cls.log.spam("POST request to MN at URL {} has status code: {}".format(mn_url, r.status_code))
            return r
        except Exception as e:
            cls.log.warning("Error attempt to send transaction to Masternode at URL {}\nerror={}".format(mn_url, e))
            return None

    @classmethod
    async def async_send_txs(cls, txs: List[TransactionBase], session):
        async def _send(url, data):
            async with session.post(url, data=data) as resp:
                return await resp.json()

        tx_containers = [TransactionContainer.create(tx).serialize() for tx in txs]
        futs = []
        for data in tx_containers:
            url = cls._get_mn_url()
            futs.append(_send(url, data))
        await asyncio.gather(*futs)

    @classmethod
    def pump_it(cls, rate: int, gen_func=None, use_poisson=True, sleep_sometimes=False, active_bounds=(120, 240),
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
            from scipy.stats import expon
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
    async def dump_it(cls, session, volume: int, delay: int=0, gen_func=None):
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
        cls.log.info("Dumping {} transactions...".format(len(txs)))
        await cls.async_send_txs(txs, session)
        # for tx in txs:
        #     cls.send_tx(tx)
        cls.log.success("Done dumping {} transactions in {} seconds".format(len(txs), round(time.time() - start, 3)))

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
    def get_random_mn_url(cls):
        return random.choice(cls.mn_urls)

    @classmethod
    def _parse_reply(cls, req, req_type='json'):
        if req.status_code != 200:
            cls.log.spam("Got status code {} from request {}".format(req.status_code, req))
            return None

        if req_type == 'json':
            return req.json()
        else:
            raise Exception("Unknown request type {}".format(req_type))

    @classmethod
    def _check_eq_replies(cls, replies: dict):
        vals = list(replies.values())
        if all(x == vals[0] for x in vals):
            return vals[0]
        else:
            cls.log.warning("Masternodes had inconsistent replies for GET requests ... possibile state"
                            " corruption!?\nReplies: {}".format(replies))
            return None

    @classmethod
    def get_from_mn_api(cls, query_str, enforce_consistency=True, req_type='json'):
        if not enforce_consistency:
            return cls._parse_reply(requests.get("{}/{}".format(cls.get_random_mn_url(), query_str)))

        replies = {}
        for mn_url in cls.mn_urls:
            req_url = "{}/{}".format(mn_url, query_str)
            replies[req_url] = cls._parse_reply(requests.get(req_url))
        return cls._check_eq_replies(replies)

    @classmethod
    async def async_get_from_mn_api(cls, query_str, session, enforce_consistency=True, req_type='json'):
        async def fetch_url(url):
            async with session.get(url) as resp:
                if req_type == 'json':
                    return await resp.json()
                elif req_type == 'text':
                    return await resp.text()
                else:
                    raise Exception("Unknown req_type {}".format(req_type))

        if not enforce_consistency:
            return await fetch_url("{}/{}".format(cls.mn_urls[0], query_str))

        replies = {}
        for mn_url in cls.mn_urls:
            req_url = "{}/{}".format(mn_url, query_str)
            replies[req_url] = fetch_url(req_url)

        results = dict(zip(replies.keys(), await asyncio.gather(*list(replies.values()))))
        return cls._check_eq_replies(results)

    @classmethod
    def submit_contract(cls, code: str, name: str, sk: str, vk: str, stamps=10**6):
        tx = PublishTransaction.create(contract_code=code,
                                       contract_name=name,
                                       sender_sk=sk,
                                       nonce=vk + secrets.token_hex(32),
                                       stamps_supplied=stamps)
        return cls.send_tx(tx)

    @classmethod
    def get_contract_names(cls) -> List[str]:
        r = cls.get_from_mn_api('contracts')
        if r is not None:
            assert 'contracts' in r, "Expected key 'contracts' to be in dict returned by /contracts endpoint. " \
                                     "Instead got {}".format(r)
            return r['contracts']
        else:
            return None

    @classmethod
    def get_contract_meta(cls, contract_name: str):
        return cls.get_from_mn_api('contracts/{}'.format(contract_name))

    @classmethod
    def get_contract_resources(cls, contract_name: str):
        return cls.get_from_mn_api('contracts/{}/resources'.format(contract_name))

    @classmethod
    def get_contract_methods(cls, contract_name: str):
        return cls.get_from_mn_api('contracts/{}/methods'.format(contract_name))

    @classmethod
    async def get_balances(cls, session, vks: list, contract_name=CURRENCY_CONTRACT_NAME) -> dict:
        async def _get_balance(vk, contract_name):
            req_url = "contracts/{}/balances/{}".format(contract_name, vk)
            return cls._process_balance_json(await God.async_get_from_mn_api(req_url, session))

        balances, fetched = {}, {}

        for vk in vks:
            balances[vk] = _get_balance(vk, contract_name=contract_name)
        results = dict(zip(balances.keys(), await asyncio.gather(*list(balances.values()))))

        for k in results:
            if results[k] is not None:
                fetched[k] = results[k]

        return fetched

    @classmethod
    def wait_for_mns_online(cls, timeout=300):
        cls.log.notice("Waiting for masternodes to come online...")
        elapsed = 0
        while True:
            try:
                cls.log.info("Checking if masternodes are online")
                val = God.get_from_mn_api('ping')
                if val is not None:
                    cls.log.notice("All masternodes online.")
                    return
            except Exception as e:
                cls.log.warning("Error checking if MNs online: {}".format(e))

            if elapsed > timeout:
                raise Exception("Timeout of {} reached waiting for masternodes to be online")

            elapsed += 5
            time.sleep(5)

    @classmethod
    async def get_balance(cls, vk, contract_name=CURRENCY_CONTRACT_NAME) -> int or None:
        req_url = "contracts/{}/balances/{}".format(contract_name, vk)
        return cls._process_balance_json(God.get_from_mn_api(req_url))

    @classmethod
    def _process_balance_json(cls, d: dict) -> int or None:
        try:
            if d:
                assert 'value' in d, "Expected key 'value' to be in reply json {}".format(d)
                return Decimal(d['value'])
            else:
                return None
        except Exception as e:
            log.critical("Got error processing balance json {} ... error:\n {}".format(d, e))


    @classmethod
    def _get_mn_url(cls):
        assert len(cls.mn_urls) > 0, "mn_urls not set!"
        mn_url = cls.mn_urls[cls._current_mn_idx]
        cls._current_mn_idx = (cls._current_mn_idx + 1) % len(cls.mn_urls)
        return mn_url

