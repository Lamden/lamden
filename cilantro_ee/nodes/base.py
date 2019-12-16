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
from multiprocessing import Queue
from cilantro_ee.nodes.masternode.webserver import start_webserver
from cilantro_ee.services.block_server import BlockServerProcess, BlockServer
from cilantro_ee.nodes.masternode.transaction_batcher import TransactionBatcher
from cilantro_ee.nodes.masternode.block_aggregator import BlockAggregatorController
import random
import os

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


class NewMasternode:
    def __init__(self, ip, ctx, signing_key, name):
        # stuff
        self.log = get_logger(name)
        self.ip = ip
        self.wallet = Wallet(seed=signing_key)
        self.zmq_ctx = ctx
        self.tx_queue = Queue()

        self.signing_key = signing_key

        conf.HOST_VK = self.wallet.verifying_key()

        self.overlay_server = OverlayServer(sk=signing_key, ctx=self.zmq_ctx, quorum=1)

        self.ipc_ip = 'mn-ipc-sock-' + str(os.getpid()) + '-' \
                      + str(random.randint(0, 2 ** 32))
        self.ipc_port = 6967  # can be chosen randomly any open port

    async def start(self):
        await self.overlay_server.start_discover()

        block_server = BlockServer(signing_key=self.signing_key)
        asyncio.ensure_future(block_server.serve())

        self.server = LProcess(target=start_webserver, name='WebServerProc', args=(self.tx_queue,))
        self.server.start()

        self.log.info("Masternode starting transaction batcher process")
        self.batcher = LProcess(target=TransactionBatcher, name='TxBatcherProc',
                                kwargs={'queue': self.tx_queue, 'ip': self.ip,
                                        'signing_key': self.signing_key,
                                        'ipc_ip': self.ipc_ip, 'ipc_port': self.ipc_port})
        self.batcher.start()

        self.log.info("Masternode starting BlockAggregator Process")
        self.block_agg = LProcess(target=BlockAggregatorController,
                                  name='BlockAgg',
                                  kwargs={'ipc_ip': self.ipc_ip,
                                          'ipc_port': self.ipc_port,
                                          'signing_key': self.signing_key})
        self.block_agg.start()

        while True:
            asyncio.sleep(0)

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
        await self.overlay_server.start_discover()
        while True:
            asyncio.sleep(0)