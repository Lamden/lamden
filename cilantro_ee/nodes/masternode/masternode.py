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
from cilantro_ee.nodes.masternode.webserver import start_webserver

from cilantro_ee.services.block_server import BlockServer
from cilantro_ee.services.overlay.network import Network, NetworkParameters, ServiceType
from cilantro_ee.services.block_fetch import BlockFetcher

from cilantro_ee.nodes.masternode.transaction_batcher import TransactionBatcher
from cilantro_ee.nodes.masternode.block_aggregator_controller import BlockAggregatorController
from cilantro_ee.utils.lprocess import LProcess
from cilantro_ee.services.storage.vkbook import VKBook
from cilantro_ee.core.sockets.socket_book import SocketBook
from cilantro_ee.nodes.masternode.new_ws import WebServer
from cilantro_ee.contracts import sync

from contracting.client import ContractingClient

import cilantro_ee
from multiprocessing import Process

cclient = ContractingClient()


class NewMasternode:
    def __init__(self, socket_base, ctx, wallet, constitution: dict, overwrite=False, bootnodes=conf.BOOTNODES,
                 network_parameters=NetworkParameters(), webserver_port=8080):
        # stuff
        self.log = get_logger()
        self.socket_base = socket_base
        self.wallet = wallet
        self.ctx = ctx
        self.network_parameters = network_parameters

        conf.HOST_VK = self.wallet.verifying_key()

        self.bootnodes = bootnodes
        self.constitution = constitution
        self.overwrite = overwrite

        # Services
        self.network = Network(wallet=self.wallet, ctx=self.ctx, socket_base=socket_base, bootnodes=self.bootnodes,
                               params=self.network_parameters)

        self.block_server = BlockServer(wallet=self.wallet, socket_base=socket_base,
                                        network_parameters=network_parameters)

        self.block_agg_controller = None

        self.tx_batcher = TransactionBatcher(wallet=wallet,
                                             ctx=self.ctx,
                                             socket_base=socket_base,
                                             network_parameters=network_parameters)

        self.webserver = WebServer(wallet=wallet, port=webserver_port)
        self.webserver_process = Process(target=self.webserver.start)

        self.vkbook = None

    async def start(self):
        # Discover other nodes

        if cclient.get_contract('vkbook') is None or self.overwrite:
            sync.extract_vk_args(self.constitution)
            sync.submit_vkbook(self.constitution, overwrite=self.overwrite)

        # Set Network Parameters
        self.vkbook = VKBook()

        self.network.initial_mn_quorum = self.vkbook.masternode_quorum_min
        self.network.initial_del_quorum = self.vkbook.delegate_quorum_min
        self.network.mn_to_find = self.vkbook.masternodes
        self.network.del_to_find = self.vkbook.delegates

        await self.network.start()

        # Sync contracts
        sync.submit_from_genesis_json_file(cilantro_ee.contracts.__path__[0] + '/genesis.json')

        # Start block server to provide catchup to other nodes
        asyncio.ensure_future(self.block_server.serve())

        block_fetcher = BlockFetcher(wallet=self.wallet, ctx=self.ctx, contacts=self.vkbook,
                                     masternode_sockets=SocketBook(socket_base=self.socket_base,
                                                                   service_type=ServiceType.BLOCK_SERVER,
                                                                   phonebook_function=self.vkbook.contract.get_masternodes,
                                                                   ctx=self.ctx))

        # Catchup
        await block_fetcher.sync()

        self.block_agg_controller = BlockAggregatorController(wallet=self.wallet,
                                                              ctx=self.ctx,
                                                              socket_base=self.socket_base,
                                                              network_parameters=self.network_parameters,
                                                              vkbook=self.vkbook)

        await self.block_agg_controller.start()

        await self.tx_batcher.start()

        #self.webserver.app.loop = asyncio.get_event_loop()
        await self.webserver.start()

        # self.webserver_process.start()

    def stop(self):
        self.block_server.stop()
        self.network.stop()
        self.block_agg_controller.stop()
        self.tx_batcher.stop()
        self.webserver.app.stop()
        # self.webserver_process.terminate()
