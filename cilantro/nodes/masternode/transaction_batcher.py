# TODO this file could perhaps be named better
from cilantro.constants.zmq_filters import WITNESS_MASTERNODE_FILTER

from cilantro.protocol.multiprocessing.worker import Worker
from cilantro.messages.transaction.ordering import OrderingContainer
import asyncio


BATCH_INTERVAL = 2  # TODO move this into a constants file


class TransactionBatcher(Worker):

    def setup(self):
        self.composer.add_pub(ip=self.ip)
        asyncio.ensure_future(self.compose_transactions())

    async def compose_transactions(self):
        self.log.important3("STARTING TRANSACTION BATCHER")
        self.log.important("Current queue size is {}".format(self.queue.qsize()))

        while True:
            self.log.important("Batcher resting for {} seconds".format(BATCH_INTERVAL))
            await asyncio.sleep(BATCH_INTERVAL)

            self.log.important("Sending {} transactions in a row".format(self.queue.qsize()))
            for _ in range(self.queue.qsize()):
                tx = self.queue.get()

                oc = OrderingContainer.create(tx=tx, masternode_vk=self.verifying_key)
                self.log.spam("mn about to pub for tx {}".format(tx))  # debug line
                self.composer.send_pub_msg(filter=WITNESS_MASTERNODE_FILTER, message=oc)

