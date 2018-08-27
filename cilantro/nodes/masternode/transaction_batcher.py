# TODO this file could perhaps be named better
from cilantro.constants.zmq_filters import WITNESS_MASTERNODE_FILTER
from cilantro.constants.ports import MN_NEW_BLOCK_PUB_PORT, MN_TX_PUB_PORT

from cilantro.protocol.multiprocessing.worker import Worker
from cilantro.messages.transaction.ordering import OrderingContainer
import asyncio


BATCH_INTERVAL = 2  # TODO move this into a constants file


class TransactionBatcher(Worker):

    def setup(self):
        self.composer.add_pub(ip=self.ip, port=MN_TX_PUB_PORT)
        asyncio.ensure_future(self.compose_transactions())

    async def compose_transactions(self):
        self.log.important("Starting TransactionBatcher")
        self.log.info("Current queue size is {}".format(self.queue.qsize()))

        while True:
            self.log.debugv("Batcher resting for {} seconds".format(BATCH_INTERVAL))
            await asyncio.sleep(BATCH_INTERVAL)

            self.log.debug("Sending {} transactions in batch".format(self.queue.qsize()))
            for _ in range(self.queue.qsize()):
                tx = self.queue.get()

                oc = OrderingContainer.create(tx=tx, masternode_vk=self.verifying_key)
                self.log.spam("masternode about to publish transaction from sender {}".format(tx.sender))
                self.composer.send_pub_msg(filter=WITNESS_MASTERNODE_FILTER, message=oc, port=MN_TX_PUB_PORT)

