from cilantro.messages import *
from cilantro.messages.transaction.contract import *
import asyncio
from cilantro.protocol.reactor import ReactorInterface
from cilantro.protocol.transport import Composer
from unittest.mock import MagicMock
from cilantro.logger import get_logger
import os, requests, time, random


if os.getenv('HOST_IP'):
    _MN_URL = "http://{}:8080".format(os.getenv('MASTERNODE', '0.0.0.0'))
else:
    _MN_URL = "http://0.0.0.0:8080"

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


class God:

    _DEFAULT_SK = '6b73b06b9faee35527f034fb1809e4fc94915a29568a708fd972fcfba20d8555'
    _DEFAULT_VK = '8ae53bad73b46a746384918dd41a9bed1410eda6d1a5fb57ec9e1b92748c6511'

    # For MP tests
    node_map = None
    testers = []

    log = get_logger("GOD")

    # Masternode URL
    mn_url = _MN_URL

    def __init__(self, loop=None):
        self.log = get_logger("GOD")

        self.loop = loop or asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        mock_router = MagicMock()
        self.interface = ReactorInterface(router=mock_router, loop=self.loop, signing_key=God._DEFAULT_SK)

        # a dict of composer_sk to composer object
        self.composers = {}

    def _get_or_create_composer(self, signing_key):
        if signing_key in self.composers:
            self.log.debug("Existing Composer object found for signing key {}".format(signing_key))
            return self.composers[signing_key]
        else:
            self.log.debug("Creating new Composer object for signing key {}".format(signing_key))
            c = Composer(interface=self.interface, signing_key=signing_key, name='God-Composer-{}'.format(signing_key[:4]))
            self.composers[signing_key] = c
            return c

    @classmethod
    def _default_gen_func(cls):
        return cls.random_contract_tx

    @classmethod
    def set_mn_url(cls, ip='localhost', port=8080):
        url = "http://{}:{}".format(ip, port)
        cls.log.info("Setting masternode URL to {}".format(url))
        cls.mn_url = url

    @classmethod
    def create_std_tx(cls, sender: tuple, receiver: tuple, amount: int) -> StandardTransaction:
        if type(receiver) is tuple:
            receiver = receiver[1]

        return StandardTransactionBuilder.create_tx(sender[0], sender[1], receiver, amount)

    @classmethod
    def create_currency_tx(cls, sender: tuple, receiver: tuple, amount: int):
        if type(receiver) is tuple:
            receiver = receiver[1]

        return ContractTransactionBuilder.create_currency_tx(sender[0], receiver, amount)

    @classmethod
    def send_std_tx(cls, sender: tuple, receiver: tuple, amount: int):
        tx = cls.create_std_tx(sender, receiver, amount)
        cls.send_tx(tx)

    @classmethod
    def send_currency_contract(cls, sender: tuple, receiver: tuple, amount:int):
        tx = cls.create_currency_tx(sender, receiver, amount)
        cls.send_tx(tx)

    @classmethod
    def send_tx(cls, tx: TransactionBase):
        r = requests.post(cls.mn_url, data=TransactionContainer.create(tx).serialize())
        cls.log.debug("POST request to MN at URL {} has status code: {}".format(cls.mn_url, r.status_code))

    @classmethod
    def pump_it(cls, rate: int, gen_func=None, use_poisson=True):
        """
        This func blocks.
        :param rate:
        :param gen_func:
        :return:
        """
        if not gen_func:
            gen_func = cls._default_gen_func()

        if use_poisson:
            from scipy.stats import poisson, expon
            rvs_func = lambda: expon.rvs(rate) - rate
        else:
            rvs_func = lambda: 1/rate

        assert callable(gen_func), "Expected a callable for 'gen_func' but got {}".format(gen_func)

        cls.log.info("Starting to pump transactions at an average of {} transactions per second".format(rate))
        cls.log.info("Using generator func {}, with use_possion={}".format(gen_func, use_poisson))

        while True:
            wait = rvs_func()

            cls.log.debugv("Sending next transaction in {} seconds".format(wait))
            time.sleep(wait)

            tx = gen_func()

            cls.log.debugv("sending transaction {}".format(tx))
            cls.send_tx(tx)
            # r = requests.post(cls.mn_url, data=TransactionContainer.create(tx).serialize())
            # cls.log.debugv("POST request got status code {}".format(r.status_code))

    @classmethod
    def dump_it(cls, volume: int, gen_func=None):
        """
        Dump it fast
        :param volume:
        :return:
        """
        assert volume > 0, "You must dump at least 1 transaction silly"

        if not gen_func:
            gen_func = cls._default_gen_func()

        cls.log.info("Generating {} transactions to dump...".format(volume))
        txs = [gen_func() for _ in range(volume)]
        cls.log.info("Done generating transactions.")

        start = time.time()
        cls.log.notice("Dumping {} transactions...")
        for tx in txs:
            cls.send_tx(tx)
        cls.log.important("Done dumping {} transactions in {} seconds".format(len(txs), round(time.time() - start, 3)))

    @classmethod
    def random_std_tx(cls):
        sender, receiver = random.sample(ALL_WALLETS, 2)
        amount = random.randint(1, 1260)

        return cls.create_std_tx(sender=sender, receiver=receiver, amount=amount)

    @classmethod
    def random_contract_tx(cls):
        sender, receiver = random.sample(ALL_WALLETS, 2)
        amount = random.randint(1, 1260)

        return cls.create_currency_tx(sender=sender, receiver=receiver, amount=amount)

    def send_block_contender(self, url, bc):
        pass

    def send_merkle_sig(self, url, merkle_sig):
        pass

    def send_status_request(self, url, status_req):
        pass
