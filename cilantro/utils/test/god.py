from cilantro.messages import *
import asyncio
from cilantro.protocol.reactor import ReactorInterface
from cilantro.protocol.transport import Composer
from unittest.mock import MagicMock
from cilantro.logger import get_logger
import os, requests


if os.getenv('HOST_IP'):
    MN_URL = "http://{}:8080".format(os.getenv('MASTERNODE', '0.0.0.0'))
else:
    MN_URL = "http://0.0.0.0:8080"

STU = ('db929395f15937f023b4682995634b9dc19b1a2b32799f1f67d6f080b742cdb1',
 '324ee2e3544a8853a3c5a0ef0946b929aa488cbe7e7ee31a0fef9585ce398502')
DAVIS = ('21fee38471799f8c2989dd81c6d46f6c2e2db6caf63efa98a093fcba064a4b62',
 'a103715914a7aae8dd8fddba945ab63a169dfe6e37f79b4a58bcf85bfd681694')
DENTON = ('9decc7f7f0b5a4fc87ab5ce700e2d6c5d51b7565923d50ea13cbf78031bb3acf',
 '20da05fdba92449732b3871cc542a058075446fedb41430ee882e99f9091cc4d')
FALCON = ('bac886e7c6e4a9fae572e170adb333b27b590157409e62d88cc0c7bc9a7b3631',
 'ed19061921c593a9d16875ca660b57aa5e45c811c8cf7af0cfcbd23faa52cbcd')


class God:

    _DEFAULT_SK = '6b73b06b9faee35527f034fb1809e4fc94915a29568a708fd972fcfba20d8555'
    _DEFAULT_VK = '8ae53bad73b46a746384918dd41a9bed1410eda6d1a5fb57ec9e1b92748c6511'

    log = get_logger("GOD")

    def __init__(self, loop=None):
        self.log = get_logger("GOD")

        self.loop = loop or asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        mock_router = MagicMock()
        self.interface = ReactorInterface(router=mock_router, loop=self.loop, verifying_key=God._DEFAULT_VK)

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
    def create_std_tx(cls, sender: tuple, receiver: tuple, amount: int) -> StandardTransaction:
        if type(receiver) is tuple:
            receiver = receiver[1]

        return StandardTransactionBuilder.create_tx(sender[0], sender[1], receiver, amount)

    @classmethod
    def send_std_tx(cls, sender: tuple, receiver: tuple, amount: int):
        tx = cls.create_std_tx(sender, receiver, amount)
        cls.send_tx(tx)

    @classmethod
    def send_tx(cls, tx: TransactionBase):
        r = requests.post(MN_URL, data=TransactionContainer.create(tx).serialize())
        cls.log.info("POST request to MN at URL {} has status code: {}".format(MN_URL, r.status_code))


    def send_block_contender(self, url, bc):
        pass

    def send_merkle_sig(self, url, merkle_sig):
        pass

    def send_status_request(self, url, status_req):
        pass

    