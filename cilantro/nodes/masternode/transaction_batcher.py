# TODO this file could perhaps be named better
from cilantro.constants.zmq_filters import WITNESS_MASTERNODE_FILTER
from cilantro.constants.ports import MN_NEW_BLOCK_PUB_PORT, MN_TX_PUB_PORT
from cilantro.constants.masternode import BATCH_INTERVAL

from cilantro.protocol.multiprocessing.worker import Worker
from cilantro.messages.transaction.ordering import OrderingContainer
from cilantro.messages.transaction.batch import TransactionBatch

import zmq.asyncio
import asyncio


class TransactionBatcher(Worker):

    def __init__(self, queue, ip, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue, self.ip = queue, ip

        # Create Pub socket to broadcast to witnesses
        self.pub_sock = self.manager.create_socket(socket_type=zmq.PUB)  # TODO set secure=True on this guy
        self.pub_sock.bind(port=MN_TX_PUB_PORT, ip=self.ip)

        # TODO create PAIR socket to orchestrate w/ main process?

        # Start main event loop
        self.loop.run_until_complete(self.compose_transactions())

    async def compose_transactions(self):
        self.log.important("Starting TransactionBatcher with a batch interval of {} seconds".format(BATCH_INTERVAL))
        self.log.debugv("Current queue size is {}".format(self.queue.qsize()))

        while True:
            self.log.spam("Batcher resting for {} seconds".format(BATCH_INTERVAL))
            await asyncio.sleep(BATCH_INTERVAL)

            tx_list = []
            self.log.debug("Sending {} transactions in batch".format(self.queue.qsize()))
            for _ in range(self.queue.qsize()):
                tx = self.queue.get()
                self.log.spam("masternode bagging transaction from sender {}".format(tx.sender))

                tx_list.append(OrderingContainer.create(tx=tx, masternode_vk=self.verifying_key))

            batch = TransactionBatch.create(transactions=tx_list)
            self.pub_sock.send_msg(msg=batch, header=WITNESS_MASTERNODE_FILTER.encode())
