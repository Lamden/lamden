from cilantro_ee.core.sockets.socket import SocketUtil
from cilantro_ee.core.utils.context import Context
from cilantro_ee.core.logger import get_logger
from cilantro_ee.services.overlay.server import OverlayServer
from cilantro_ee.utils.lprocess import LProcess
from cilantro_ee.constants import ports
from cilantro_ee.constants import conf
from cilantro_ee.core.crypto.wallet import Wallet
import asyncio
import time

class NodeBase(Context):

    def __init__(self, ip, signing_key, name='Node'):
        super().__init__(signing_key=signing_key, name=name)
        
        SocketUtil.clear_domain_register()

        self.log = get_logger(name)
        self.ip = ip
        self.wallet = Wallet(seed=signing_key)

        conf.HOST_VK = self.wallet.verifying_key()

        self.log.info("Starting node components")

        self.log.info("Starting overlay service")
        self.overlay_server = OverlayServer(sk=signing_key, ctx=self.zmq_ctx, quorum=1)

        self.start()

    def start(self):
        self.overlay_server.start()
        self.start_node()

    def start_node(self):
        pass


class Node2:
    def __init__(self, ip, ctx, signing_key, name):
        # stuff
        self.log = get_logger(name)
        self.ip = ip
        self.wallet = Wallet(seed=signing_key)
        self.zmq_ctx = ctx

        conf.HOST_VK = self.wallet.verifying_key()

        self.overlay_server = OverlayServer(sk=signing_key, ctx=self.zmq_ctx, quorum=1)

    async def start(self):
        await self.overlay_server.discover()
