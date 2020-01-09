import asyncio
from cilantro_ee.core.block_server import BlockServer

from cilantro_ee.nodes.masternode.transaction_batcher import TransactionBatcher
from cilantro_ee.storage import CilantroStorageDriver
from cilantro_ee.sockets.services import multicast
from cilantro_ee.nodes.masternode.webserver import WebServer
from cilantro_ee.nodes.masternode.block_contender import Aggregator
from cilantro_ee.networking.parameters import ServiceType
from cilantro_ee.core import canonical


from cilantro_ee.nodes.base import Node


class Masternode(Node):
    def __init__(self, webserver_port=8080, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.blocks = CilantroStorageDriver(key=self.wallet.verifying_key())

        # Services
        self.block_server = BlockServer(
            wallet=self.wallet,
            socket_base=self.socket_base,
            network_parameters=self.network_parameters
        )

        self.webserver = WebServer(wallet=self.wallet, port=webserver_port)

        self.tx_batcher = TransactionBatcher(wallet=self.wallet, queue=[])

        self.current_nbn = canonical.get_genesis_block()

        self.aggregator = Aggregator(
            socket_id=self.network_parameters.resolve(
                self.socket_base,
                service_type=ServiceType.BLOCK_AGGREGATOR,
                bind=True),
            ctx=self.ctx,
            driver=self.driver
        )

    async def start(self):
        await super().start()

        # Start block server to provide catchup to other nodes
        asyncio.ensure_future(self.block_server.serve())

        self.webserver.queue = self.tx_batcher.queue

        await self.webserver.start()

    def delegate_work_sockets(self):
        return list(self.parameters.get_delegate_sockets(service=ServiceType.INCOMING_WORK).values())

    def nbn_sockets(self):
        return list(self.parameters.get_all_sockets(service=ServiceType.BLOCK_NOTIFICATIONS).values())

    def sbcs_to_block(self, subblocks):
        block = canonical.block_from_subblocks(
            subblocks,
            previous_hash=self.driver.latest_block_hash,
            block_num=self.driver.latest_block_num + 1
        )
        return block

    async def new_blockchain_boot(self):
        while len(self.tx_batcher.queue) == 0 and len(self.nbn_inbox.q) == 0:
            await asyncio.sleep(0)

        if len(self.tx_batcher.queue) > 0:
            msg = canonical.dict_to_msg_block(canonical.get_genesis_block())
            await multicast(self.ctx, msg, self.nbn_sockets())

    async def join_quorum(self):
        # Catchup with NBNs until you have work, the join the quorum
        while len(self.tx_batcher.queue) == 0 or len(self.nbn_inbox.q) == 0:
            nbn = await self.nbn_inbox.wait_for_next_nbn()

            # Update with state
            self.driver.update_with_block(nbn)
            self.blocks.store_new_block(nbn)

        await self.process_blocks()

    async def run(self):
        if self.driver.latest_block_num == 0:
            await self.new_blockchain_boot()
        else:
            await self.join_quorum()

    async def process_blocks(self):
        while self.running:
            # Else, batch some more txs
            tx_batch = self.tx_batcher.pack_current_queue()

            await self.parameters.refresh() # Works
            await multicast(self.ctx, tx_batch, self.delegate_work_sockets()) # Works

            # this really should just give us a block straight up
            block = await self.aggregator.gather_subblocks(
                total_contacts=len(self.contacts.delegates),
                expected_subblocks=len(self.contacts.masternodes)
            )

            # Update with state
            self.driver.update_with_block(block)
            self.blocks.store_new_block(block)

            is_skip_block = canonical.block_is_skip_block(block)

            # If so, hang until you get a new block or some work
            while is_skip_block or len(self.tx_batcher.queue) <= 0:
                await asyncio.sleep(0)

            # Pack current NBN into message
            await multicast(self.ctx, canonical.dict_to_msg_block(block), self.nbn_sockets())

    def stop(self):
        super().stop()

        self.block_server.stop()
        self.webserver.app.stop()
