from cilantro_ee.core.nonces import NonceManager
from cilantro_ee.messages.message_type import MessageType
from cilantro_ee.messages.message import Message
from cilantro_ee.constants.batcher import BATCHER_SLEEP_INTERVAL, MAX_TXN_SUBMISSION_DELAY, MAX_TXNS_PER_SUB_BLOCK

import hashlib
import asyncio
import time


class RateLimiter:
    def __init__(self, wallet,
                 queue=[],
                 sleep_interval=BATCHER_SLEEP_INTERVAL,
                 max_batch_size=MAX_TXNS_PER_SUB_BLOCK,
                 max_txn_delay=MAX_TXN_SUBMISSION_DELAY):

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
        num_txns = len(self.queue)

        if num_txns > 0:
            self.txn_delay += 1

        if self.num_batches_sent >= 2 or \
                (self.num_batches_sent > 0 and
                 (num_txns < self.max_batch_size or self.txn_delay < self.max_txn_submission_delay)):
            return False

        return True

    def get_next_batch_size(self):
        num_txns = len(self.queue)

        if (num_txns >= self.max_batch_size) or \
           (self.txn_delay >= self.max_txn_submission_delay):

            self.txn_delay = 0
            return min(num_txns, self.max_batch_size)

        return 0

    def get_txn_list(self, batch_size):
        tx_list = []
        for _ in range(batch_size):
            # Get a transaction from the queue
            tx = self.queue.pop(0)
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