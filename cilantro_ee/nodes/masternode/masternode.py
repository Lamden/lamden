import asyncio
from cilantro_ee.logger.base import get_logger
from cilantro_ee.constants import conf

from cilantro_ee.core.block_server import BlockServer
from cilantro_ee.networking.network import Network
from cilantro_ee.core.block_fetch import BlockFetcher

from cilantro_ee.nodes.masternode.transaction_batcher import TransactionBatcher
from cilantro_ee.storage.vkbook import VKBook
from cilantro_ee.sockets.socket_book import SocketBook
from cilantro_ee.nodes.masternode.webserver import WebServer
from cilantro_ee.contracts import sync
from cilantro_ee.nodes.masternode.block_contender import Aggregator
from cilantro_ee.networking.parameters import Parameters, ServiceType, NetworkParameters
from cilantro_ee.crypto.transforms import subblock_contender_list_to_block
from contracting.client import ContractingClient

import zmq.asyncio
import cilantro_ee

cclient = ContractingClient()


class NewMasternode:
    def __init__(self, socket_base, ctx: zmq.asyncio.Context, wallet, constitution: dict, overwrite=False,
                 bootnodes=conf.BOOTNODES, network_parameters=NetworkParameters(), webserver_port=8080):
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
        self.network = Network(
            wallet=self.wallet,
            ctx=self.ctx,
            socket_base=socket_base,
            bootnodes=self.bootnodes,
            params=self.network_parameters
        )

        self.block_server = BlockServer(
            wallet=self.wallet,
            socket_base=socket_base,
            network_parameters=network_parameters
        )

        self.block_agg_controller = None

        self.tx_batcher = TransactionBatcher(wallet=wallet, queue=[])

        self.webserver = WebServer(wallet=wallet, port=webserver_port)

        self.vkbook = None

        self.parameters = Parameters(socket_base, ctx, wallet, network_parameters, None)
        self.current_nbn = None
        self.running = True

        self.aggregator = Aggregator()

        self.nbn_inbox = NBNInbox()

    async def start(self):
        # Discover other nodes

        if cclient.get_contract('vkbook') is None or self.overwrite:
            sync.extract_vk_args(self.constitution)
            sync.submit_vkbook(self.constitution, overwrite=self.overwrite)

        # Set Network Parameters
        self.vkbook = VKBook()
        self.parameters.contacts = self.vkbook

        self.network.initial_mn_quorum = self.vkbook.masternode_quorum_min
        self.network.initial_del_quorum = self.vkbook.delegate_quorum_min
        self.network.mn_to_find = self.vkbook.masternodes
        self.network.del_to_find = self.vkbook.delegates

        await self.network.start()

        # Sync contracts
        sync.submit_from_genesis_json_file(cilantro_ee.contracts.__path__[0] + '/genesis.json')

        # Start block server to provide catchup to other nodes
        asyncio.ensure_future(self.block_server.serve())

        block_fetcher = BlockFetcher(
            wallet=self.wallet,
            ctx=self.ctx,
            contacts=self.vkbook,
            masternode_sockets=SocketBook(
                socket_base=self.socket_base,
                service_type=ServiceType.BLOCK_SERVER,
                phonebook_function=self.vkbook.contract.get_masternodes,
                ctx=self.ctx
            )
        )

        # Catchup
        await block_fetcher.sync()

        self.webserver.queue = self.tx_batcher.queue

        await self.webserver.start()

    async def send_out(self, msg, socket_id):
        socket = self.ctx.socket(zmq.DEALER)
        socket.connect(str(socket_id))

        try:
            socket.send(msg, zmq.NOBLOCK)
            return True
        except zmq.ZMQError:
            return False

    async def send_batch_to_delegates(self):
        tx_batch = self.tx_batcher.pack_current_queue()

        await self.parameters.refresh()

        # Send out messages to delegates
        tasks = []
        for k, v in self.parameters.get_delegate_sockets(service=ServiceType.TX_BATCHER):
            tasks.append(self.send_out(tx_batch, v))

        await asyncio.gather(*tasks)

    async def send_nbn_to_everyone(self):
        # Send out current NBN to everyone
        tasks = []
        for k, v in self.parameters.get_all_sockets(service=ServiceType.BLOCK_NOTIFICATIONS):
            tasks.append(self.send_out(self.current_nbn, v))

        await asyncio.gather(*tasks)

        self.current_nbn = None

    async def process_blocks(self):
        await self.nbn_inbox.wait_for_next_nbn()

        while self.running:
            # Else, batch some more txs
            await self.send_batch_to_delegates()

            subblocks = await self.aggregator.gather_subblocks(quorum=1)
            block = subblock_contender_list_to_block(subblocks)

            self.current_nbn = block

            # If entire block is empty
            if kind == BNKind.SKIP:
                await self.nbn_inbox.wait_for_next_nbn()

            await self.send_nbn_to_everyone()

    def stop(self):
        self.block_server.stop()
        self.network.stop()
        self.block_agg_controller.stop()
        self.webserver.app.stop()
