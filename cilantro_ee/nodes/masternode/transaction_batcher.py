from cilantro_ee.constants.zmq_filters import TRANSACTION_FILTERS
from cilantro_ee.constants.ports import MN_TX_PUB_PORT
from cilantro_ee.constants.batcher import BATCHER_SLEEP_INTERVAL
from cilantro_ee.constants.batcher import MAX_TXN_SUBMISSION_DELAY
from cilantro_ee.constants.batcher import MAX_TXNS_PER_SUB_BLOCK

from cilantro_ee.core.utils.worker import Worker
from cilantro_ee.core.messages.message_type import MessageType
from cilantro_ee.core.messages.message import Message
from cilantro_ee.core.crypto.wallet import Wallet, _verify
from cilantro_ee.core.utils.transaction import transaction_is_valid, TransactionException
from cilantro_ee.core.nonces import NonceManager
from cilantro_ee.core.sockets.services import AsyncInbox, SocketStruct, Protocols
from multiprocessing import Queue
import zmq.asyncio
import asyncio
import time
import hashlib

IPC_ID = '/tmp/masternode-input-hash-inbox'
IPC_PORT = 6967

'''
Dynamically rate limits transaction batches so that the Trnasaction Batcher can just await responses and not have to
worry about DDOS attacked or TX flooding.
'''


class NewTransactionBatcher:
    def __init__(self, publisher_ip: str, wallet: Wallet, ctx: zmq.asyncio.Context, queue: Queue=Queue(),ipc_id: str=IPC_ID):
        self.wallet = wallet
        self.queue = queue
        self.ctx = ctx
        self.publisher_ip = publisher_ip
        self.ipc_id = SocketStruct(protocol=Protocols.ICP, id=ipc_id)

        self.ready = False
        self.running = False

        self.input_hash_inbox = InputHashInbox(parent=self, socket_id=self.ipc_id, wallet=wallet, ctx=self.ctx)

        self.batcher = RateLimitingBatcher(self.queue, self.wallet,
                                           BATCHER_SLEEP_INTERVAL,
                                           MAX_TXNS_PER_SUB_BLOCK,
                                           MAX_TXN_SUBMISSION_DELAY)

        self.publisher = self.ctx.socket(zmq.PUB)
        self.publisher.bind(f'tcp://{self.publisher_ip}:{MN_TX_PUB_PORT}')

    async def start(self):
        self.running = True
        asyncio.ensure_future(self.input_hash_inbox.serve())

        while not self.ready and self.running:
            await asyncio.sleep(0)

        asyncio.ensure_future(self.compose_transactions())

    async def compose_transactions(self):
        sub_filter = TRANSACTION_FILTER.encode()

        while self.running:
            mtype, msg = await self.batcher.get_next_batch_packed()
            self.publisher.send(mtype + msg)

    def stop(self):
        self.running = False
        self.input_hash_inbox.stop()
        self.batcher.running = False


class InputHashInbox(AsyncInbox):
    def __init__(self, parent: NewTransactionBatcher, *args, **kwargs):
        self.parent = parent
        super().__init__(*args, **kwargs)

    async def handle_msg(self, _id, msg):
        msg_type, msg, sender, timestamp, is_verified = Message.unpack_message_2(message=msg)

        if not is_verified:
            return

        if msg_type == MessageType.BURN_INPUT_HASHES:
            self.parent.batcher.remove_batch_ids(msg.inputHashes)

        elif msg_type == MessageType.READY:
            self.parent.ready = True


class RateLimitingBatcher:
    def __init__(self, queue, wallet, sleep_interval,
                 max_batch_size, max_txn_delay):

        self.queue = queue
        self.wallet = wallet
        self.batcher_sleep_interval = sleep_interval
        self.max_batch_size = max_batch_size
        self.max_txn_submission_delay = max_txn_delay

        self.driver = NonceManager()
        self.num_batches_sent = 0
        self.txn_delay = 0
        self.tasks = []
        self.sent_batch_ids = []

        self.running = True

    def add_batch_id(self, batch_id):
        self.sent_batch_ids.append(batch_id)
        self.num_batches_sent += 1

    # async def remove_batch_ids(self, batch_ids):
    def remove_batch_ids(self, batch_ids):
        self.num_batches_sent -= 1

        for id in batch_ids:
            while id in self.sent_batch_ids:
                self.sent_batch_ids.pop(0)

        list_len = len(self.sent_batch_ids)

        if list_len < self.num_batches_sent:
            self.num_batches_sent = list_len

    def ready_for_next_batch(self):
        num_txns = self.queue.qsize()

        if num_txns > 0:
            self.txn_delay += 1

        if self.num_batches_sent >= 2 or \
                (self.num_batches_sent > 0 and
                 (num_txns < self.max_batch_size or self.txn_delay < self.max_txn_submission_delay)):
            return False

        return True

    def get_next_batch_size(self):
        num_txns = self.queue.qsize()

        if (num_txns >= self.max_batch_size) or \
           (self.txn_delay >= self.max_txn_submission_delay):

            self.txn_delay = 0
            return min(num_txns, self.max_batch_size)

        return 0

    def get_txn_list(self, batch_size):
        tx_list = []
        for _ in range(batch_size):
            # Get a transaction from the queue
            tx = self.queue.get()


            # Make sure that the transaction is valid
            # this is better done at webserver level before packing and putting it into the queue - raghu todo
            try:
                transaction_is_valid(tx=tx[1],
                                     expected_processor=self.wallet.verifying_key(),
                                     driver=self.driver,
                                     strict=True)
            except TransactionException as e:
                continue

            tx_list.append(tx[1])

        return tx_list

    def pack_txn_list(self, tx_list):
        h = hashlib.sha3_256()
        for tx in tx_list:
            # Hash it
            tx_bytes = tx.as_builder().to_bytes_packed()
            h.update(tx_bytes)

        # Add a timestamp
        timestamp = time.time()
        h.update('{}'.format(timestamp).encode())
        inputHash = h.digest()

        # Make explicit, only being used once
        self.add_batch_id(inputHash)

        # Sign the message for verification
        signature = self.wallet.sign(inputHash)

        mtype, msg = Message.get_message_packed(
                         MessageType.TRANSACTION_BATCH,
                         transactions=[t for t in tx_list], timestamp=timestamp,
                         signature=signature, inputHash=inputHash,
                         sender=self.wallet.verifying_key())

        # self.log.debug1("Send {} transactions with hash {} and timestamp {}"
                        # .format(len(tx_list), inputHash.hex(), timestamp))

        return mtype, msg

    async def get_next_batch_packed(self):
        while not self.ready_for_next_batch() and self.running:
            await asyncio.sleep(self.batcher_sleep_interval)

            # Add to interval here... easier

        # Make this explicit. not being used elsewhere
        num_txns = self.get_next_batch_size()

        tx_list = self.get_txn_list(num_txns)

        mtype, msg = self.pack_txn_list(tx_list)

        return mtype, msg



class TransactionBatcher(Worker):
    def __init__(self, ip, signing_key, queue=Queue(), ipc_ip=IPC_ID, ipc_port=IPC_PORT, *args, **kwargs):
        super().__init__(signing_key=signing_key, *args, **kwargs)
        self.ip = ip
        self.ipc_ip = ipc_ip
        self.ipc_port = ipc_port

        self.batcher = RateLimitingBatcher(queue, self.wallet,
                                           BATCHER_SLEEP_INTERVAL,
                                           MAX_TXNS_PER_SUB_BLOCK,
                                           MAX_TXN_SUBMISSION_DELAY)

        self._ready = False

        self.driver = NonceManager()

# Are we even using this anymore?
        # Create Pub socket to broadcast to witnesses
        self.pub_sock = self.manager.create_socket(socket_type=zmq.PUB, name="TxBatcher-PUB", secure=True)
        self.pub_sock.bind(port=MN_TX_PUB_PORT, ip=self.ip)

        # Create DEALER socket to talk to the BlockManager process over IPC
        self.ipc_dealer = None
        self._create_dealer_ipc(port=ipc_port, ip=ipc_ip, identity=str(0).encode())

        self.run()

    def run(self):
        self.log.notice("Starting TransactionBatcher ...")
        self.tasks.append(self.compose_transactions())

        # Start main event loop
        # self.loop.run_until_complete(self.compose_transactions())
        self.loop.run_until_complete(asyncio.gather(*self.tasks))

    def _create_dealer_ipc(self, port: int, ip: str, identity: bytes):
        self.ipc_dealer = self.manager.create_socket(socket_type=zmq.DEALER, name="Batcher-IPC-Dealer[{}]".format(0), secure=False)
        self.ipc_dealer.setsockopt(zmq.IDENTITY, identity)

        self.tasks.append(self.ipc_dealer.add_handler(handler_func=self.handle_ipc_msg))

    def _connect_dealer_ipc(self):
        self.log.notice("Connecting to BA's ROUTER socket with a DEALER using"
                        " ip {}, port {}".format(self.ipc_ip, self.ipc_port))
        self.ipc_dealer.connect(port=self.ipc_port, protocol='ipc', ip=self.ipc_ip)

    def handle_ipc_msg(self, frames):
        assert len(frames) == 2, "Expected 2 frames: (msg_type, msg_blob). Got {} instead.".format(frames)

        msg_type = frames[0]
        msg_blob = frames[1]

        msg_type, msg, sender, timestamp, is_verified = Message.unpack_message(msg_type, msg_blob)
        if not is_verified:
            self.log.error("Failed to verify the message of type {} from {} at {}. Ignoring it .."
                          .format(msg_type, sender, timestamp))
            return

        self.log.info('Got message on IPC {}'.format(msg_type))

        if msg_type == MessageType.BURN_INPUT_HASHES:
            self.log.info('An empty or non-empty block was made.')
            self.batcher.remove_batch_ids(msg.inputHashes)

        elif msg_type == MessageType.READY:
            self.log.success('READY.')
            self._ready = True

        else:
            self.log.error("Batcher got unexpected message type {} from BA's IPC "
                           "socket. Ignoring the msg {}".format(type(msg), msg))

    async def _wait_until_ready(self):
        await asyncio.sleep(1)
        self._connect_dealer_ipc()
        await asyncio.sleep(3)
        while not self._ready:
            await asyncio.sleep(1)

    async def compose_transactions(self):
        await self._wait_until_ready()

        self.log.notice("TransactionBatcher is ready to send transactions ...")

        enc_fltr = TRANSACTION_FILTERS[0].encode()

        while True:
            mtype, msg = await self.batcher.get_next_batch_packed()
            self.pub_sock.send_msg(msg=msg, msg_type=mtype, filter=enc_fltr)
            self.log.info("Sent next batch ...")


