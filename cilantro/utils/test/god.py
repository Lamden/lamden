from cilantro.messages.transaction.container import TransactionContainer
from cilantro.messages.transaction.contract import *
from cilantro.messages.signals.kill_signal import KillSignal
from cilantro.constants.system_config import *
from unittest.mock import MagicMock
from cilantro.logger import get_logger
from cilantro.utils.test.mp_test_case import MPTestCase
import os, requests, time, random, asyncio


if os.getenv('HOST_IP'):
    ips = os.getenv('MASTERNODE', '0.0.0.0')
    # Set _MN_URL to be a list of IPs if we are in multimaster setting
    if ',' in ips:
        ips = ips.split(',')
    else:
        ips = [ips]

    urls = ["http://{}:8080".format(ip) for ip in ips]
    _MN_URLs = urls

# If this is not getting run on a container, set MN URL to 0.0.0.0
else:
    _MN_URLs = ["http://0.0.0.0:8080"]

STU = ('db929395f15937f023b4682995634b9dc19b1a2b32799f1f67d6f080b742cdb1',
 '324ee2e3544a8853a3c5a0ef0946b929aa488cbe7e7ee31a0fef9585ce398502')
DAVIS = ('21fee38471799f8c2989dd81c6d46f6c2e2db6caf63efa98a093fcba064a4b62',
 'a103715914a7aae8dd8fddba945ab63a169dfe6e37f79b4a58bcf85bfd681694')
DENTON = ('9decc7f7f0b5a4fc87ab5ce700e2d6c5d51b7565923d50ea13cbf78031bb3acf',
 '20da05fdba92449732b3871cc542a058075446fedb41430ee882e99f9091cc4d')
FALCON = ('bac886e7c6e4a9fae572e170adb333b27b590157409e62d88cc0c7bc9a7b3631',
 'ed19061921c593a9d16875ca660b57aa5e45c811c8cf7af0cfcbd23faa52cbcd')
CARL = ('cf67a180f9578afa5fd704cea39b450c1542755d73614f6a4f41b627190b83bb',
 'cb9bfd4b57b243248796e9eb90bc4f0053d78f06ce68573e0fdca422f54bb0d2')
RAGHU = ('b44a8cc3dcadbdb3352ea046ec85cd0f6e8e3f584e3d6eb3bd10e142d84a9668',
 'c1f845ad8967b93092d59e4ef56aef3eba49c33079119b9c856a5354e9ccdf84')

ALL_WALLETS = [STU, DAVIS, DENTON, FALCON, CARL, RAGHU]


def int_to_padded_bytes(i: int) -> bytes:
    SIZE = 32
    s = str(i)
    assert len(s) <= SIZE, "int {} is too long!".format(s)

    padding = SIZE - len(s)
    s = '0'*padding + s
    b = s.encode()

    assert len(b) == SIZE, "{} is not size {}".format(b, SIZE)

    return s.encode()


if SHOULD_MINT_WALLET:
    for i in range(NUM_WALLETS_TO_MINT):
        sk, vk = wallet.new(int_to_padded_bytes(i))
        ALL_WALLETS.append((sk, vk))

def countdown(duration: int, msg: str, log=None, status_update_freq=5):
    _l = log or get_logger("Countdown")
    if duration > status_update_freq:
        num_sleeps = duration // status_update_freq

        for _ in range(num_sleeps):
            time.sleep(status_update_freq)
            duration -= status_update_freq
            _l.important3(msg.format(duration))

    if duration > 0:
        time.sleep(duration)


class God:

    _DEFAULT_SK = '6b73b06b9faee35527f034fb1809e4fc94915a29568a708fd972fcfba20d8555'
    _DEFAULT_VK = '8ae53bad73b46a746384918dd41a9bed1410eda6d1a5fb57ec9e1b92748c6511'

    # For MP tests
    node_map = None
    testers = []

    log = get_logger("GOD")

    mn_urls = _MN_URLs
    multi_master = type(mn_urls) is list  # If True, outgoing transactions will be round-robined to all masternodes
    _current_mn_idx = 0

    def __init__(self, loop=None):
        raise NotImplementedError("use class methods. __init__ does not work rn")

    @classmethod
    def teardown_all(cls, masternode_url):
        masternode_url += '/teardown-network'
        cls.log.important("Sending teardown notification to Masternode at url {}".format(masternode_url))
        r = requests.post(masternode_url, data=KillSignal.create().serialize())

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
    def pump_it(cls, rate: int, gen_func=None, use_poisson=True):
        """
        Pump random transactions from random users to Masternode's REST endpoint at an average rate of 'rate'
        transactions per second. This func blocks.
        :param rate:
        :param gen_func:
        :return:
        """
        if not gen_func:
            gen_func = cls._default_gen_func()

        if use_poisson:
            from scipy.stats import poisson, expon
            rvs_func = lambda: expon.rvs(rate)/rate - 1
        else:
            rvs_func = lambda: 1/rate

        assert callable(gen_func), "Expected a callable for 'gen_func' but got {}".format(gen_func)

        cls.log.important("Starting to pump transactions at an average of {} transactions per second".format(rate))
        cls.log.info("Using generator func {}, with use_possion={}".format(gen_func, use_poisson))

        while True:
            wait = rvs_func()

            cls.log.spam("Sending next transaction in {} seconds".format(wait))
            time.sleep(wait)

            tx = gen_func()

            cls.log.spam("sending transaction {}".format(tx))
            cls.send_tx(tx)

    @classmethod
    def dump_it(cls, volume: int, delay: int=0, gen_func=None):
        """
        Dump it fast. Send
        :param volume:
        :return:
        """
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
