from cilantro_ee.nodes.work_inbox import WorkInbox
from cilantro_ee.networking.parameters import ServiceType

from cilantro_ee.messages.message import Message
from cilantro_ee.messages.message_type import MessageType

from cilantro_ee.nodes.delegate import execution
from cilantro_ee.sockets.outbox import Peers, MN
import heapq

from cilantro_ee.nodes.base import Node
from cilantro_ee.logger.base import get_logger
import asyncio

from contracting.execution.executor import Executor


class Delegate(Node):
    def __init__(self, parallelism=4, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # Number of core / processes we push to
        self.parallelism = parallelism
        self.executor = Executor(driver=self.driver)

        self.work_inbox = WorkInbox(
            socket_id=self.network_parameters.resolve(self.socket_base, ServiceType.INCOMING_WORK, bind=True),
            driver=self.driver,
            ctx=self.ctx,
            contacts=self.parameters.get_masternode_vks(),
            wallet=self.wallet
        )

        self.pending_sbcs = set()

        self.log = get_logger(f'DEL {self.wallet.vk_pretty[4:12]}')

        self.masternode_socket_book = Peers(
            wallet=self.wallet,
            ctx=self.ctx,
            parameters=self.parameters,
            service_type=ServiceType.BLOCK_AGGREGATOR,
            node_type=MN
        )

    async def start(self):
        await super().start()

        asyncio.ensure_future(self.work_inbox.serve())
        asyncio.ensure_future(self.run())

        self.log.info('Running...')

    def masternode_aggregator_sockets(self):
        return list(self.parameters.get_masternode_sockets(service=ServiceType.BLOCK_AGGREGATOR).values())

    def mn_agg_skcs(self):
        return list(self.parameters.get_masternode_sockets(service=ServiceType.BLOCK_AGGREGATOR).items())

    def did_sign_block(self, block):
        if len(self.pending_sbcs) == 0:
            return False

        # Throws a failure if even one of the subblocks isnt signed.
        # This can be fixed in the future with partial blocks.
        for sub_block in block['subBlocks']:
            if sub_block['merkleLeaves'][0] not in self.pending_sbcs:
                return False

        # Returns true if its an empty block. Not sure if that is intended?
        return True

    def process_nbn(self, nbn):
        self.log.error(f'DEL UPDATING FOR BLOCK NUM {self.driver.latest_block_num}')

        self.driver.reads.clear()
        self.driver.pending_writes.clear()

        if self.driver.latest_block_num < nbn['blockNum'] and nbn['hash'] != b'\xff' * 32:
            self.driver.update_with_block(nbn)
            self.issue_rewards(block=nbn)
            self.update_sockets()

        self.nbn_inbox.clean()
        # self.pending_sbcs.clear()
        self.nbn_inbox.update_signers()

    # def process_upg_msg(self):
    # possibly for ready
    #     pass

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
        self.masternode_socket_book.sync_sockets()

        if len(self.parameters.sockets) == 0:
            return

        self.log.error(f'{len(self.parameters.get_masternode_vks())} MNS!')

        work = await self.work_inbox.wait_for_next_batch_of_work(
            current_contacts=self.parameters.get_masternode_vks()
        )


        self.log.info(f'Got {len(work)} batch(es) of work')

        return self.filter_work(work)

    def process_work(self, filtered_work):
        results = execution.execute_work(
            executor=self.executor,
            driver=self.driver,
            work=filtered_work,
            wallet=self.wallet,
            previous_block_hash=self.driver.latest_block_hash,
            stamp_cost=self.reward_manager.stamps_per_tau
        )

        # Add merkle roots to track successful sbcs
        # for sb in results:
        #     self.pending_sbcs.add(sb.merkleTree.leaves[0])

        self.log.info(results)

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
            self.version_check()

        while self.running:
            await self.parameters.refresh()
            self.masternode_socket_book.sync_sockets()

            filtered_work = await self.acquire_work()

            self.log.info(filtered_work)

            sbc_msg = self.process_work(filtered_work)

            await self.masternode_socket_book.send_to_peers(
                msg=sbc_msg
            )

            #await self.parameters.refresh()
            #self.masternode_socket_book.sync_sockets()

            nbn = await self.nbn_inbox.wait_for_next_nbn()
            self.process_nbn(nbn)

    def stop(self):
        self.running = False
        self.network.stop()
        self.work_inbox.stop()
        self.nbn_inbox.stop()
