# TODO this file could perhaps be named better
from cilantro.constants.system_config import TRANSACTIONS_PER_SUB_BLOCK
from cilantro.constants.zmq_filters import WITNESS_MASTERNODE_FILTER
from cilantro.constants.ports import MN_NEW_BLOCK_PUB_PORT, MN_TX_PUB_PORT
from cilantro.constants.system_config import BATCH_INTERVAL, MAX_SKIP_TURNS

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
        self.pub_sock = self.manager.create_socket(socket_type=zmq.PUB, name="TxBatcherPUB", secure=True)
        self.pub_sock.bind(port=MN_TX_PUB_PORT, ip=self.ip)

        # TODO create PAIR socket to orchestrate w/ main process?

        # Start main event loop
        self.loop.run_until_complete(self.compose_transactions())

    async def compose_transactions(self):
        self.log.important("Starting TransactionBatcher with a batch interval of {} seconds".format(BATCH_INTERVAL))
        self.log.debugv("Current queue size is {}".format(self.queue.qsize()))

        skip_turns = MAX_SKIP_TURNS
        while True:
            self.log.spam("Batcher resting for {} seconds".format(BATCH_INTERVAL))
            await asyncio.sleep(BATCH_INTERVAL)

            num_txns = self.queue.qsize()
            tx_list = []
            if (num_txns >= TRANSACTIONS_PER_SUB_BLOCK) or (skip_turns < 1):
                for _ in range(min(TRANSACTIONS_PER_SUB_BLOCK, num_txns)):
                    tx = self.queue.get()
                    self.log.spam("masternode bagging transaction from sender {}".format(tx.sender))

                    tx_list.append(OrderingContainer.create(tx=tx, masternode_vk=self.verifying_key))
                    skip_turns = MAX_SKIP_TURNS  # reset to max again
            else:
                skip_turns = skip_turns - 1
                continue

            # send either empty or some txns capping at TRANSACTIONS_PER_SUB_BLOCK
            self.log.debug("Sending {} transactions in batch".format(len(tx_list)))
            batch = TransactionBatch.create(transactions=tx_list)
            self.pub_sock.send_msg(msg=batch, header=WITNESS_MASTERNODE_FILTER.encode())
