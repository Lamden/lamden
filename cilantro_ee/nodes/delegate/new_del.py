import asyncio
from cilantro_ee.crypto import Wallet
from cilantro_ee.core.logger import get_logger
from cilantro_ee.constants import conf
from cilantro_ee.services.overlay.server import OverlayServer


class NewDelegate:
    def __init__(self, ip, ctx, signing_key, name):
        # stuff
        self.log = get_logger(name)
        self.ip = ip
        self.wallet = Wallet(seed=signing_key)
        self.zmq_ctx = ctx

        conf.HOST_VK = self.wallet.verifying_key()

        self.overlay_server = OverlayServer(sk=signing_key, ctx=self.zmq_ctx, quorum=1)

    async def start(self):
        await self.overlay_server.start_discover()
        while True:
            asyncio.sleep(0)