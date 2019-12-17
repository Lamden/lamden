# Start Overlay Server / Discover
# Run Catchup
# Start Block Agg
# Start Block Man
# Start Webserver
import asyncio
from multiprocessing import Queue
from cilantro_ee.core.crypto.wallet import Wallet
from cilantro_ee.core.logger import get_logger
from cilantro_ee.constants import conf
from cilantro_ee.services.overlay.server import OverlayServer
from cilantro_ee.nodes.masternode.webserver import start_webserver

from cilantro_ee.services.block_server import BlockServer
from cilantro_ee.services.block_fetch import BlockFetcher

from cilantro_ee.nodes.masternode.transaction_batcher import TransactionBatcher
from cilantro_ee.nodes.masternode.block_aggregator import BlockAggregatorController
from cilantro_ee.utils.lprocess import LProcess
from cilantro_ee.services.storage.vkbook import VKBook
from cilantro_ee.contracts import sync

import random
import os


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

        self.overlay_server = None

        self.ipc_ip = 'mn-ipc-sock-' + str(os.getpid()) + '-' + str(random.randint(0, 2 ** 32))
        self.ipc_port = 6967  # can be chosen randomly any open port

        # Services
        self.block_server = BlockServer(signing_key=self.signing_key)

        self.server = LProcess(target=start_webserver, name='WebServerProc', args=(self.tx_queue,))

        self.batcher = LProcess(target=TransactionBatcher, name='TxBatcherProc',
                                kwargs={'queue': self.tx_queue, 'ip': self.ip,
                                        'signing_key': self.signing_key,
                                        'ipc_ip': self.ipc_ip, 'ipc_port': self.ipc_port})

        self.block_agg = LProcess(target=BlockAggregatorController,
                                  name='BlockAgg',
                                  kwargs={'ipc_ip': self.ipc_ip,
                                          'ipc_port': self.ipc_port,
                                          'signing_key': self.signing_key})

    async def start(self, exclude=('vkbook',)):
        # Discover other nodes
        # masternodes, delegates = sync.get_masternodes_and_delegates_from_constitution()
        # sync.submit_vkbook({
        #     'masternodes': masternodes,
        #     'delegates': delegates
        # })

        sync.seed_vkbook()

        self.overlay_server = OverlayServer(sk=self.signing_key, ctx=self.zmq_ctx, quorum=1, vkbook=VKBook())
        await self.overlay_server.start_discover()

        # Start block server to provide catchup to other nodes
        asyncio.ensure_future(self.block_server.serve())

        # Sync contracts
        sync.sync_genesis_contracts(exclude=exclude)

        # Make sure a VKBook exists in state


        # Run Catchup
        #block_fetcher = BlockFetcher()

        self.server.start()

        self.log.info("Masternode starting transaction batcher process")

        self.batcher.start()

        self.log.info("Masternode starting BlockAggregator Process")

        self.block_agg.start()

        while True:
            asyncio.sleep(0)

    def stop(self):
        self.block_server.stop()
        self.overlay_server.stop()
        self.server.terminate()
        self.batcher.terminate()
        self.block_agg.terminate()
