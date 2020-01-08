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

        self.current_nbn = None

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

    async def process_first_block(self):
        if self.driver.latest_block_num == 0:
            done = False
            while not done:
                if len(self.tx_batcher.queue) > 0:
                    print('tx in q')
                    await multicast(self.ctx, self.current_nbn, self.nbn_sockets())
                    done = True
                if len(self.nbn_inbox.q) > 0:
                    done = True
        else:
            await self.nbn_inbox.wait_for_next_nbn()

    async def process_blocks(self):
        # Someone just joining the network should wait until the next block to join
        await self.process_first_block()

        while self.running:
            # Else, batch some more txs
            tx_batch = self.tx_batcher.pack_current_queue()

            await self.parameters.refresh() # Works
            await multicast(self.ctx, tx_batch, self.delegate_work_sockets()) # Works

            # Subblocks is a mapping between subblock index and subblock. If the subblock failed, it will be none
            subblocks = await self.aggregator.gather_subblocks(
                total_contacts=len(self.contacts.delegates),
                expected_subblocks=len(self.contacts.masternodes)
            ) # Works

            is_skip_block = False
            # Block is not failed block
            if None not in subblocks.values():
                # Must
                block = canonical.block_from_subblocks(
                    [v for _, v in sorted(subblocks.items())],
                    previous_hash=self.driver.latest_block_hash,
                    block_num=self.driver.latest_block_num + 1
                ) # Idk

                # Update with state
                self.driver.update_with_block(block)

                # Store
                self.blocks.store_new_block(block)

                is_skip_block = canonical.block_is_skip_block(block)
            else:
                print('failed')
                block = canonical.get_failed_block(
                    previous_hash=self.driver.latest_block_hash,
                    block_num=self.driver.latest_block_num + 1
                )

            # Serialize as Capnp again
            self.current_nbn = block

            # If so, hang until you get a new block or some work
            while is_skip_block or len(self.tx_batcher.queue) <= 0:
                await asyncio.sleep(0)

            await multicast(self.ctx, self.current_nbn, self.nbn_sockets())
            self.current_nbn = None

    def stop(self):
        self.block_server.stop()
        self.network.stop()
        self.webserver.app.stop()
