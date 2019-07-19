# TODO this file could perhaps be named better
from cilantro_ee.messages.base.base import MessageBase
from cilantro_ee.constants.system_config import TRANSACTIONS_PER_SUB_BLOCK
from cilantro_ee.constants.zmq_filters import TRANSACTION_FILTER
from cilantro_ee.constants.ports import MN_TX_PUB_PORT
from cilantro_ee.constants.system_config import BATCH_SLEEP_INTERVAL, NUM_BLOCKS
from cilantro_ee.messages.signals.master import EmptyBlockMade, NonEmptyBlockMade
from cilantro_ee.messages.signals.node import Ready
from cilantro_ee.utils.utils import int_to_bytes, bytes_to_int

from cilantro_ee.protocol.multiprocessing.worker import Worker
from cilantro_ee.messages.transaction.ordering import OrderingContainer
from cilantro_ee.messages.transaction.batch import TransactionBatch

import zmq.asyncio
import asyncio, time, os


class TransactionBatcher(Worker):

    def __init__(self, queue, ip, ipc_ip, ipc_port, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue, self.ip = queue, ip
        self.ipc_ip = ipc_ip
        self.ipc_port = ipc_port
        self._ready = False

        # Create Pub socket to broadcast to witnesses
        self.pub_sock = self.manager.create_socket(socket_type=zmq.PUB, name="TxBatcher-PUB", secure=True)
        self.pub_sock.bind(port=MN_TX_PUB_PORT, ip=self.ip)

        # Create DEALER socket to talk to the BlockManager process over IPC
        self.ipc_dealer = None
        self._create_dealer_ipc(port=ipc_port, ip=ipc_ip, identity=str(0).encode())

        self.num_bags_sent = 0

        self.tasks.append(self.compose_transactions())

        # Start main event loop
        # self.loop.run_until_complete(self.compose_transactions())
        self.loop.run_until_complete(asyncio.gather(*self.tasks))

    def _create_dealer_ipc(self, port: int, ip: str, identity: bytes):
        self.ipc_dealer = self.manager.create_socket(socket_type=zmq.DEALER, name="Batcher-IPC-Dealer[{}]".format(0), secure=False)
        self.ipc_dealer.setsockopt(zmq.IDENTITY, identity)

        self.tasks.append(self.ipc_dealer.add_handler(handler_func=self.handle_ipc_msg))

    def _connect_dealer_ipc(self):
        self.log.info("Connecting to BlockAggregator's ROUTER socket with a DEALER using ip {}, port {}"
                      .format(self.ipc_ip, self.ipc_port))
        self.ipc_dealer.connect(port=self.ipc_port, protocol='ipc', ip=self.ipc_ip)


    def handle_ipc_msg(self, frames):
        assert len(frames) == 2, "Expected 2 frames: (msg_type, msg_blob). Got {} instead.".format(frames)

        msg_type = bytes_to_int(frames[0])
        msg_blob = frames[1]

        msg = MessageBase.registry[msg_type].from_bytes(msg_blob) # How messages get deserialized.
        self.log.debugv("Batcher received an IPC message {}".format(msg))

        if isinstance(msg, EmptyBlockMade):
            self.num_bags_sent = self.num_bags_sent - 1

        elif isinstance(msg, NonEmptyBlockMade):
            self.num_bags_sent = self.num_bags_sent - 1

        elif isinstance(msg, Ready):
            self.log.spam("Got Ready notif from block aggregator!!!")
            self._ready = True

        else:
            raise Exception("Batcher got message type {} from IPC dealer socket that it does not know how to handle"
                            .format(type(msg)))

    async def _wait_until_ready(self):
        await asyncio.sleep(1)
        self._connect_dealer_ipc()
        while not self._ready:
            await asyncio.sleep(1)


    async def compose_transactions(self):

        await self._wait_until_ready()

        self.log.important("Starting TransactionBatcher")
        self.log.debugv("Current queue size is {}".format(self.queue.qsize()))

        max_num_bags = 3 * NUM_BLOCKS    # ideally, num_caches * num_blocks
        normal_bag = TRANSACTIONS_PER_SUB_BLOCK
        half_bag = normal_bag // 2
        quarter_bag = normal_bag // 4
        double_bag = 2 * normal_bag

        while True:
            num_txns = self.queue.qsize() 
            if (self.num_bags_sent > max_num_bags) or \
               ((num_txns < half_bag) and (self.num_bags_sent > 2)) or \
               ((num_txns < quarter_bag) and (self.num_bags_sent > 1)):
                await asyncio.sleep(BATCH_SLEEP_INTERVAL)
                continue

            tx_list = []
            bag_size =  min(normal_bag if self.num_bags_sent <  max_num_bags else double_bag, num_txns)
            for _ in range(bag_size):
                tx = OrderingContainer.from_bytes(self.queue.get())
                # self.log.spam("masternode bagging transaction from sender {}".format(tx.transaction.sender))
                tx_list.append(tx)

            batch = TransactionBatch.create(transactions=tx_list)
            self.pub_sock.send_msg(msg=batch, header=TRANSACTION_FILTER.encode())
            self.num_bags_sent = self.num_bags_sent + NUM_BLOCKS
            if len(tx_list):
                self.log.spam("Sending {} transactions in batch".format(len(tx_list)))
            else:
                self.log.debug3("Sending an empty transaction batch")

