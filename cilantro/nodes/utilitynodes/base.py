from cilantro.protocol.reactor import ReactorInterface
from cilantro.protocol.transport import Composer
from cilantro.protocol.wallets import ED25519Wallet
from cilantro.logger import get_logger
import os, uuid, asyncio

class BaseNode:
    def __init__(self, *args, **kwargs):
        self.log = get_logger("BaseNode")
        self.log.info("-- BaseNode Initiating --")
        self.port = int(os.getenv('PORT', 31337))
        self.host = os.getenv('HOST_IP', '127.0.0.1')
        self.loop = asyncio.get_event_loop()
        self.reactor = ReactorInterface(self, self.loop)
        self.wallet = ED25519Wallet()
        self.composer = Composer(self.reactor, self.wallet.s, uuid.uuid4().hex)
