from cilantro.protocol import wallet
from cilantro.protocol.utils.socket import SocketUtil
from cilantro.utils.keys import Keys
from cilantro.utils import is_valid_hex

import asyncio, zmq, zmq.asyncio


# common context for each process
class Context:

    def __init__(self, signing_key=None, name=''):
        assert is_valid_hex(signing_key, 64), "signing_key must a 64 char hex str not {}".format(signing_key)
        name = name or type(self).__name__

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.zmq_ctx = zmq.asyncio.Context()

        # raghu todo do we need this below ??
        self.signing_key = signing_key
        Keys.setup(sk_hex=signing_key)
        # raghu todo do we need this below ??
        self.verifying_key = wallet.get_vk(self.signing_key)

        SocketUtil.setup(Keys.public_key.hex())


