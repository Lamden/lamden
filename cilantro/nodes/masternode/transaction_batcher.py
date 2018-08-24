# TODO this file could perhaps be named better
from cilantro.protocol.multiprocessing.worker import Worker
import asyncio


class TransactionBatcher(Worker):

    def setup(self):
        # TODO create PUB socket here to send stuff out to witnesses. remove the other pub socket created in masternode state machine
        asyncio.ensure_future(self.compose_transactions())

    async def compose_transactions(self):
        self.log.important3("STARTING TRANSACTION BATCHER")
        while True:
            self.log.important("Current queue size is {}".format(self.queue.qsize()))
            # TODO batch these things and send them out. self.queue is a multiprocessing.Queue object,
            # and all sanic workers are stuffing the data get get from rest requests into this queue
            await asyncio.sleep(2)

