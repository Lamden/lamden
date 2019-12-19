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
from cilantro_ee.nodes.masternode.block_aggregator import BlockAggregatorController
from cilantro_ee.utils.lprocess import LProcess
from cilantro_ee.services.storage.vkbook import VKBook
from cilantro_ee.core.sockets.socket_book import SocketBook

from cilantro_ee.contracts import sync

from contracting.client import ContractingClient

import cilantro_ee

cclient = ContractingClient()


class NewMasternode:
    def __init__(self, socket_base, ctx, wallet, constitution: dict, overwrite=False, bootnodes=conf.BOOTNODES,
                 network_parameters=NetworkParameters()):
        # stuff
        self.log = get_logger()
        self.socket_base = socket_base
        self.wallet = wallet
        self.ctx = ctx
        self.network_parameters = NetworkParameters()
        #self.tx_queue = Queue()

        conf.HOST_VK = self.wallet.verifying_key()

        self.bootnodes = bootnodes
        self.constitution = constitution
        self.overwrite = overwrite

        # Services
        self.network = Network(wallet=self.wallet, ctx=self.ctx, socket_base=socket_base, bootnodes=self.bootnodes,
                               params=self.network_parameters)

        self.block_server = BlockServer(wallet=self.wallet, socket_base=socket_base,
                                        network_parameters=network_parameters)

    async def start(self):
        # Discover other nodes

        if cclient.get_contract('vkbook') is None:
            sync.extract_vk_args(self.constitution)
            sync.submit_vkbook(self.constitution, overwrite=self.overwrite)

        # Set Network Parameters
        vkbook = VKBook()

        self.network.initial_mn_quorum = vkbook.masternode_quorum_min
        self.network.initial_del_quorum = vkbook.delegate_quorum_min
        self.network.mn_to_find = vkbook.masternodes
        self.network.del_to_find = vkbook.delegates

        await self.network.start()

        # Sync contracts
        sync.submit_from_genesis_json_file(cilantro_ee.contracts.__path__[0] + '/genesis.json')

        # Start block server to provide catchup to other nodes
        asyncio.ensure_future(self.block_server.serve())

        block_fetcher = BlockFetcher(wallet=self.wallet, ctx=self.ctx,
                                     masternode_sockets=SocketBook(socket_base=self.socket_base,
                                                                   service_type=ServiceType.BLOCK_SERVER,
                                                                   phonebook_function=vkbook.contract.get_masternodes,
                                                                   ctx=self.ctx))

        await block_fetcher.sync()

        print('done')

    def sync_genesis_contracts(self):
        pass

    def stop(self):
        #self.block_server.stop()
        self.network.stop()
