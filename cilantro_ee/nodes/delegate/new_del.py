import asyncio
from multiprocessing import Queue
from cilantro_ee.core.crypto.wallet import Wallet
from cilantro_ee.core.logger import get_logger
from cilantro_ee.constants import conf
from cilantro_ee.services.overlay.server import OverlayServer
from cilantro_ee.nodes.masternode.webserver import start_webserver
from cilantro_ee.services.block_server import BlockServerProcess, BlockServer
from cilantro_ee.nodes.masternode.transaction_batcher import TransactionBatcher
from cilantro_ee.nodes.masternode.block_aggregator import BlockAggregatorController
from cilantro_ee.utils.lprocess import LProcess

import random
import os


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