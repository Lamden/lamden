# TODO this file could perhaps be named better
from cilantro.protocol.multiprocessing.worker import Worker
import asyncio


class TransactionBatcher(Worker):

    def setup(self):
        asyncio.ensure_future(self.compose_transactions())

    async def compose_transactions(self):
        self.log.important3("STARTING TRANSACTION BATCHER")
        while True:
            self.log.important("(live from raghu proc) Current queue size is {}".format(self.queue.qsize()))
            await asyncio.sleep(2)

