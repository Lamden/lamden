# TODO this file could perhaps be named better
from cilantro_ee.messages.base.base import MessageBase
from cilantro_ee.constants.system_config import TRANSACTIONS_PER_SUB_BLOCK
from cilantro_ee.constants.zmq_filters import TRANSACTION_FILTER
from cilantro_ee.constants.ports import MN_TX_PUB_PORT
from cilantro_ee.constants.system_config import BATCH_SLEEP_INTERVAL, NUM_BLOCKS
from cilantro_ee.messages.signals.node import Ready
from cilantro_ee.messages.base import base
from cilantro_ee.utils.utils import int_to_bytes, bytes_to_int
from cilantro_ee.protocol.multiprocessing.worker import Worker
from cilantro_ee.messages.transaction.contract import ContractTransaction
from cilantro_ee.messages.transaction.batch import TransactionBatch
from cilantro_ee.messages._new.message import MessageTypes
import zmq.asyncio
import asyncio, time, os
import os
import capnp
from cilantro_ee.messages import capnp as schemas
import hashlib
from cilantro_ee.messages._new.message import MessageTypes
from cilantro_ee.utils.utils import int_to_bytes, bytes_to_int
from cilantro_ee.protocol.wallet import Wallet

blockdata_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/blockdata.capnp')
subblock_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/subblock.capnp')
envelope_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/envelope.capnp')
transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')
signal_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/signals.capnp')

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
        #msg_blob = frames[1]

        self.log.info('Got message on IPC {}'.format(msg_type))

        if msg_type == MessageTypes.EMPTY_BLOCK_MADE or msg_type == MessageTypes.NON_EMPTY_BLOCK_MADE:
            self.num_bags_sent = self.num_bags_sent - 1
            self.log.info('An empty or non-empty block was made.')

        elif msg_type == MessageTypes.READY_INTERNAL:
            self.log.success('READY.')
            self._ready = True

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

            bag_size = min(normal_bag if self.num_bags_sent < max_num_bags else double_bag, num_txns)

            timestamp = time.time()

            h = hashlib.sha3_256()

            # Timestamp is used for input hash
            #h.update('{}'.format(timestamp).encode())

            for _ in range(bag_size):
                # Get a transaction from the queue
                tx = self.queue.get()

                # Hash it
                tx_bytes = tx.as_builder().to_bytes_packed()
                h.update(tx_bytes)

                # Deserialize it and put it in the list
                #tx = transaction_capnp.ContractTransaction.from_bytes_packed(t)
                tx_list.append(tx)

            batch = transaction_capnp.TransactionBatch.new_message()
            batch.init('transactions', len(tx_list))
            for i, tx in enumerate(tx_list):
                batch.transactions[i] = tx

            # Sign the message for verification
            w = Wallet(seed=self.signing_key)
            batch.signature = w.sign(h.digest())
            batch.sender = w.verifying_key()

            # Add a timestamp
            batch.timestamp = timestamp

            self.pub_sock.send_msg(msg=batch.to_bytes_packed(),
                                   msg_type=int_to_bytes(MessageTypes.TRANSACTION_BATCH),
                                   filter=TRANSACTION_FILTER.encode())

            self.num_bags_sent = self.num_bags_sent + NUM_BLOCKS
            if len(tx_list):
                self.log.spam("Sending {} transactions in batch".format(len(tx_list)))
            else:
                self.log.debug3("Sending an empty transaction batch")

