import asyncio
from cilantro_ee.catchup import BlockServer

from cilantro_ee.nodes.masternode.transaction_batcher import TransactionBatcher
from cilantro_ee.storage import CilantroStorageDriver
from cilantro_ee.sockets.services import multicast, secure_multicast
from cilantro_ee.nodes.masternode.webserver import WebServer
from cilantro_ee.nodes.masternode.block_contender import Aggregator
from cilantro_ee.networking.parameters import ServiceType
from cilantro_ee import canonical

from cilantro_ee.nodes.base import Node
from cilantro_ee.logger.base import get_logger


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

        self.webserver = WebServer(wallet=self.wallet, port=webserver_port, driver=self.driver)
        self.tx_batcher = TransactionBatcher(wallet=self.wallet, queue=[])
        self.current_nbn = canonical.get_genesis_block()

        self.aggregator = Aggregator(
            socket_id=self.network_parameters.resolve(
                self.socket_base,
                service_type=ServiceType.BLOCK_AGGREGATOR,
                bind=True),
            ctx=self.ctx,
            driver=self.driver,
            wallet=self.wallet
        )

    async def start(self):
        await super().start()
        # Start block server to provide catchup to other nodes
        asyncio.ensure_future(self.block_server.serve())
        self.webserver.queue = self.tx_batcher.queue
        await self.webserver.start()
        asyncio.ensure_future(self.aggregator.start())
        asyncio.ensure_future(self.run())

    def delegate_work_sockets(self):
        return list(self.parameters.get_delegate_sockets(service=ServiceType.INCOMING_WORK).values())

    def nbn_sockets(self):
        return list(self.parameters.get_all_sockets(service=ServiceType.BLOCK_NOTIFICATIONS).values())

    def dl_wk_sks(self):
        return list(self.parameters.get_delegate_sockets(service=ServiceType.INCOMING_WORK).items())

    def nbn_sks(self):
        return list(self.parameters.get_all_sockets(service=ServiceType.BLOCK_NOTIFICATIONS).items())

    async def run(self):
        self.log.info('Running...')
        if self.driver.latest_block_num == 0:
            await self.new_blockchain_boot()
        else:
            await self.join_quorum()

    async def new_blockchain_boot(self):
        self.log.info('Fresh blockchain boot.')
        while len(self.tx_batcher.queue) == 0 and len(self.nbn_inbox.q) == 0:
            if not self.running:
                return
            await asyncio.sleep(0)

        if len(self.tx_batcher.queue) > 0:
            await self.parameters.refresh()
            msg = canonical.dict_to_msg_block(canonical.get_genesis_block())

            await secure_multicast(
                wallet=self.wallet,
                ctx=self.ctx,
                msg=msg,
                peers=self.nbn_sks()
            )

            # await multicast(self.ctx, msg, self.nbn_sockets())

        self.driver.set_latest_block_num(1)
        await self.process_blocks()

    async def join_quorum(self):
        # Catchup with NBNs until you have work, the join the quorum
        self.log.info('Join Quorum')
        nbn = await self.nbn_inbox.wait_for_next_nbn()

        # Update with state
        self.driver.update_with_block(nbn)
        self.driver.commit()
        self.blocks.put(nbn, self.blocks.BLOCK)

        while len(self.tx_batcher.queue) == 0:
            await asyncio.sleep(0)
            if len(self.nbn_inbox.q) > 0:
                nbn = self.nbn_inbox.q.pop(0)
                self.driver.update_with_block(nbn)
                self.blocks.put(nbn, self.blocks.BLOCK)

        await self.process_blocks()

    async def send_work(self):
        # Else, batch some more txs
        self.log.info(f'Sending {len(self.tx_batcher.queue)} transactions.')
        tx_batch = self.tx_batcher.pack_current_queue()

        await self.parameters.refresh()

        # No one is online
        if len(self.dl_wk_sks()) == 0:
            self.log.error('No one online!')
            return

        return await secure_multicast(
            wallet=self.wallet,
            ctx=self.ctx,
            msg=tx_batch,
            peers=self.dl_wk_sks()
        )

        # return await multicast(self.ctx, tx_batch, self.delegate_work_sockets())  # Works

    async def wait_for_work(self, block):
        is_skip_block = canonical.block_is_skip_block(block)

        if is_skip_block:
            self.log.info('SKIP. Going to hang now...')

        # If so, hang until you get a new block or some work OR NBN
        self.nbn_inbox.clean()

        while is_skip_block and len(self.tx_batcher.queue) <= 0:
            if len(self.nbn_inbox.q) > 0:
                break

            await asyncio.sleep(0)

    def process_block(self, block):
        #do_not_store = canonical.block_is_failed(block, self.driver.latest_block_hash, self.driver.latest_block_num + 1)
        #do_not_store |= canonical.block_is_skip_block(block)

        # if not do_not_store:
        if block['blockNum'] != self.driver.latest_block_num and block['blockHash'] != b'\xff' * 32:

            self.driver.update_with_block(block)
            self.issue_rewards(block=block)
            
            self.driver.reads.clear()
            self.driver.pending_writes.clear()

            self.update_sockets()

            # STORE IT IN THE BACKEND
            self.blocks.put(block, self.blocks.BLOCK)
            del block['_id']

        self.nbn_inbox.clean()
        self.nbn_inbox.update_signers()

    async def process_blocks(self):
        while self.running:
            sends = await self.send_work()

            if sends is None:
                return

            self.log.error(f'{len(self.contacts.masternodes)} MNS!')

            # this really should just give us a block straight up
            block = await self.aggregator.gather_subblocks(
                total_contacts=len(self.contacts.delegates),
                expected_subblocks=len(self.contacts.masternodes)
            )

            self.process_block(block)

            await self.wait_for_work(block)

            # Pack current NBN into message
            await secure_multicast(
                wallet=self.wallet,
                ctx=self.ctx,
                msg=canonical.dict_to_msg_block(block),
                peers=self.nbn_sks()
            )

            # await multicast(self.ctx, canonical.dict_to_msg_block(block), self.nbn_sockets())

    def stop(self):
        super().stop()
        self.block_server.stop()
        self.webserver.app.stop()
