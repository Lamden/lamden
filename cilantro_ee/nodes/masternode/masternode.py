import asyncio
from cilantro_ee.logger.base import get_logger
from cilantro_ee.constants import conf

from cilantro_ee.core.block_server import BlockServer
from cilantro_ee.networking.network import Network
from cilantro_ee.core.block_fetch import BlockFetcher

from cilantro_ee.nodes.new_block_inbox import NBNInbox
from cilantro_ee.nodes.masternode.transaction_batcher import TransactionBatcher
from cilantro_ee.storage import VKBook, MetaDataStorage, CilantroStorageDriver
from cilantro_ee.sockets.socket_book import SocketBook
from cilantro_ee.sockets.services import send_out
from cilantro_ee.nodes.masternode.webserver import WebServer
from cilantro_ee.contracts import sync
from cilantro_ee.nodes.masternode.block_contender import Aggregator
from cilantro_ee.networking.parameters import Parameters, ServiceType, NetworkParameters
from cilantro_ee.core import canonical
from contracting.client import ContractingClient

import zmq.asyncio
import cilantro_ee

class NewMasternode:
    def __init__(self, socket_base, ctx: zmq.asyncio.Context, wallet, constitution: dict, overwrite=False,
                 bootnodes=conf.BOOTNODES, network_parameters=NetworkParameters(), webserver_port=8080, client=ContractingClient()):
        # Seed state initially
        if client.get_contract('vkbook') is None or overwrite:
            sync.extract_vk_args(constitution)
            sync.submit_vkbook(constitution, overwrite=overwrite)

        self.contacts = VKBook()

        self.parameters = Parameters(socket_base, ctx, wallet, contacts=self.contacts)

        # stuff
        self.log = get_logger()
        self.socket_base = socket_base
        self.wallet = wallet
        self.ctx = ctx
        self.network_parameters = network_parameters

        self.bootnodes = bootnodes
        self.constitution = constitution
        self.overwrite = overwrite

        self.driver = MetaDataStorage()
        self.blocks = CilantroStorageDriver(key=self.wallet.verifying_key())
        self.client = client

        # Services
        self.block_server = BlockServer(
            wallet=self.wallet,
            socket_base=socket_base,
            network_parameters=network_parameters
        )

        self.block_fetcher = BlockFetcher(
            wallet=self.wallet,
            ctx=self.ctx,
            contacts=self.contacts,
            masternode_sockets=SocketBook(
                socket_base=self.socket_base,
                service_type=ServiceType.BLOCK_SERVER,
                phonebook_function=self.contacts.contract.get_masternodes,
                ctx=self.ctx
            )
        )

        self.webserver = WebServer(wallet=wallet, port=webserver_port)

        self.tx_batcher = TransactionBatcher(wallet=wallet, queue=[])

        self.network = Network(
            wallet=self.wallet,
            ctx=self.ctx,
            socket_base=socket_base,
            bootnodes=self.bootnodes,
            params=self.network_parameters,
            initial_del_quorum=self.contacts.delegate_quorum_min,
            initial_mn_quorum=self.contacts.masternode_quorum_min,
            mn_to_find=self.contacts.masternodes,
            del_to_find=self.contacts.delegates,
        )

        self.current_nbn = None
        self.running = True

        self.aggregator = Aggregator(
            socket_id=self.network_parameters.resolve(
                self.socket_base,
                service_type=ServiceType.BLOCK_AGGREGATOR,
                bind=True),
            ctx=self.ctx,
            driver=self.driver
        )

        self.nbn_inbox = NBNInbox(
            socket_id=self.network_parameters.resolve(
                self.socket_base,
                service_type=ServiceType.BLOCK_NOTIFICATIONS,
                bind=True),
            ctx=self.ctx,
            driver=self.driver,
            contacts=self.contacts
        )

    async def start(self):
        await self.network.start()

        # Sync contracts
        sync.submit_from_genesis_json_file(cilantro_ee.contracts.__path__[0] + '/genesis.json')

        # Start block server to provide catchup to other nodes
        asyncio.ensure_future(self.block_server.serve())

        # Catchup
        await self.block_fetcher.sync()

        self.webserver.queue = self.tx_batcher.queue

        await self.webserver.start()

        await self.process_blocks()

    async def send_batch_to_delegates(self):
        tx_batch = self.tx_batcher.pack_current_queue()

        # Send out messages to delegates
        tasks = []
        for k, v in self.parameters.get_delegate_sockets(service=ServiceType.INCOMING_WORK).items():
            tasks.append(send_out(self.ctx, tx_batch, v))

        return await asyncio.gather(*tasks)

    async def send_nbn_to_everyone(self):
        # Send out current NBN to everyone
        tasks = []
        for k, v in self.parameters.get_all_sockets(service=ServiceType.BLOCK_NOTIFICATIONS).items():
            tasks.append(send_out(self.ctx, self.current_nbn, v))

        return await asyncio.gather(*tasks)

    def boot_up_start_blocks(self):
        # Check to see if you have blocks (catch up before this)
        # If not, hang until you have transactions in the batch or a NBN comes through
        # Send the genesis NBN and your work
        # Flip a bool to never do this again after this.
        pass

    def sbcs_to_block(self, subblocks):
        block = canonical.block_from_subblocks(
            subblocks,
            previous_hash=self.driver.latest_block_hash,
            block_num=self.driver.latest_block_num + 1
        )
        return block

    async def process_blocks(self):
        # Someone just joining the network should wait until the next block to join
        await self.nbn_inbox.wait_for_next_nbn()

        while self.running:
            # Else, batch some more txs
            await self.parameters.refresh() # Works

            # Do stuff with the results if anyone was offline
            await self.send_batch_to_delegates() # Works

            # Subblocks is a mapping between subblock index and subblock. If the subblock failed, it will be none
            subblocks = await self.aggregator.gather_subblocks(total_contacts=len(self.contacts.delegates)) # Works

            # Must
            block = canonical.block_from_subblocks(
                subblocks,
                previous_hash=self.driver.latest_block_hash,
                block_num=self.driver.latest_block_num + 1
            ) # Idk

            # Update with state
            self.driver.update_with_block(block)

            # Store
            self.blocks.store_new_block(block)

            is_skip_block = canonical.block_is_skip_block(block)

            # Serialize as Capnp again
            self.current_nbn = block

            # If so, hang until you get a new block or some work
            while is_skip_block and len(self.tx_batcher.queue) <= 0:
                await asyncio.sleep(0)

            await self.send_nbn_to_everyone()
            self.current_nbn = None

    def stop(self):
        self.block_server.stop()
        self.network.stop()
        self.webserver.app.stop()
