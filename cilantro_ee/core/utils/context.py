from cilantro_ee.core.crypto import wallet
from cilantro_ee.core.sockets.socket import SocketUtil
from cilantro_ee.utils.keys import Keys
from cilantro_ee.utils import is_valid_hex
from cilantro_ee.core.crypto.wallet import Wallet
import asyncio, zmq, zmq.asyncio


# common context for each process
class Context:

    def __init__(self, signing_key=None, name=''):
        assert is_valid_hex(signing_key, 64), "signing_key must a 64 char hex str not {}".format(signing_key)
        name = name or type(self).__name__

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.zmq_ctx = zmq.asyncio.Context()

        self.signing_key = signing_key
        self.verifying_key = wallet.get_vk(signing_key)

        signing_key = bytes.fromhex(signing_key)
        self.wallet = Wallet(seed=signing_key)

        Keys.setup(sk_hex=self.signing_key)
        SocketUtil.setup(Keys.public_key.hex())


