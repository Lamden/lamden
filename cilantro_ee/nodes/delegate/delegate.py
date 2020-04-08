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
import capnp
import os
import time
from cilantro_ee.messages.capnp_impl import capnp_struct as schemas

transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')


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

        self.work_inbox.accepting_work = True

        work = await self.work_inbox.wait_for_next_batch_of_work(
            current_contacts=self.parameters.get_masternode_vks()
        )

        self.work_inbox.accepting_work = False

        self.log.info(f'Got {len(work)} batch(es) of work')

        # If the number of batches is less than the number of masternodes, add shims.
        # If timeout is hit, just pad the rest of the expected amounts with empty tx batches?
        expected_masters = set(self.contacts.masternodes)

        for task in work:
            try:
                expected_masters.remove(task.sender.hex())
            except KeyError:
                self.log.error('Unauthorized work!')

        for missing_master in expected_masters:
            self.log.info(f'Adding shim tx batch for {missing_master}.')
            shim = transaction_capnp.TransactionBatch.new_message(
                transactions=[],
                timestamp=time.time(),
                signature=b'\x00' * 64,
                inputHash=missing_master,
                sender=missing_master
            )
            work.append(shim)

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
            self.process_block(nbn)
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

            nbn = await self.nbn_inbox.wait_for_next_nbn()
            self.process_block(nbn)

    def stop(self):
        self.running = False
        self.network.stop()
        self.work_inbox.stop()
        self.nbn_inbox.stop()
