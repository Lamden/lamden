from cilantro_ee.nodes.work_inbox import WorkInbox
from cilantro_ee.core.nonces import NonceManager
from cilantro_ee.core.canonical import block_is_failed
from cilantro_ee.networking.parameters import ServiceType

from cilantro_ee.messages.message import Message
from cilantro_ee.messages.message_type import MessageType

from cilantro_ee.nodes.delegate import execution
from cilantro_ee.sockets.services import multicast
import heapq

from cilantro_ee.nodes.base import Node
import asyncio

class Delegate(Node):
    def __init__(self, parallelism=4, nonces=NonceManager(), *args, **kwargs):

        super().__init__(*args, **kwargs)

        # Number of core / processes we push to
        self.parallelism = parallelism

        self.nonces = nonces

        self.work_inbox = WorkInbox(
            socket_id=self.network_parameters.resolve(self.socket_base, ServiceType.INCOMING_WORK, bind=True),
            nonces=self.nonces,
            ctx=self.ctx,
            contacts=self.parameters.get_masternode_vks(),
            wallet=self.wallet
        )

        self.pending_sbcs = set()

    async def start(self):
        await super().start()
        asyncio.ensure_future(self.run())

    def masternode_aggregator_sockets(self):
        return list(self.parameters.get_masternode_sockets(service=ServiceType.BLOCK_AGGREGATOR).values())

    def did_sign_block(self, block):
        if len(self.pending_sbcs) == 0:
            return False

        # Throws a failure if even one of the subblocks isnt signed.
        # This can be fixed in the future with partial blocks.
        for sub_block in block['subBlocks']:
            if sub_block['merkleRoot'] not in self.pending_sbcs:
                return False

        # Returns true if its an empty block. Not sure if that is intended?
        return True

    def process_nbn(self, nbn):
        if not self.did_sign_block(nbn):
            self.client.raw_driver.revert()
            self.driver.update_with_block(nbn)
        elif not block_is_failed(nbn):
            self.client.raw_driver.commit()
            self.driver.update_with_block(nbn, commit_tx=False)
        else:
            self.client.raw_driver.revert()

        self.pending_sbcs.clear()

    def filter_work(self, work):
        filtered_work = []
        for tx_batch in work:
            # Filter out None responses
            if tx_batch is None:
                continue

            # Add the rest to a priority queue based on their timestamp
            heapq.heappush(filtered_work, (tx_batch.timestamp, tx_batch))

        return filtered_work

    async def acquire_work(self):
        await self.parameters.refresh()

        if len(self.parameters.sockets) == 0:
            return

        work = await self.work_inbox.wait_for_next_batch_of_work(
            current_contacts=self.parameters.get_masternode_vks()
        )
        self.work_inbox.work.clear()

        return self.filter_work(work)

    def process_work(self, filtered_work):
        results = execution.execute_work(
            client=self.client,
            driver=self.driver,
            work=filtered_work,
            wallet=self.wallet,
            previous_block_hash=self.driver.latest_block_hash
        )

        # Add merkle roots to track successful sbcs
        for sb in results:
            self.pending_sbcs.add(sb.merkleTree.leaves[0])

        # Send out the contenders to masternodes
        return Message.get_message_packed_2(
            msg_type=MessageType.SUBBLOCK_CONTENDERS,
            contenders=[sb for sb in results]
        )

    async def run(self):
        # If first block, just wait for masters to send the genesis NBN
        if self.driver.latest_block_num == 0:
            nbn = await self.nbn_inbox.wait_for_next_nbn()
            self.process_nbn(nbn)

        while self.running:
            filtered_work = await self.acquire_work()

            sbc_msg = self.process_work(filtered_work)

            await multicast(self.ctx, sbc_msg, self.masternode_aggregator_sockets())

            nbn = await self.nbn_inbox.wait_for_next_nbn()
            self.process_nbn(nbn)

    def stop(self):
        self.running = False
        self.network.stop()
        self.work_inbox.stop()
        self.nbn_inbox.stop()
