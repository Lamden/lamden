from cilantro_ee.protocol.comm.services import AsyncInbox
from cilantro_ee.core.messages.message import Message
from cilantro_ee.core.messages.message_type import MessageType
from cilantro_ee.protocol.transaction import transaction_is_valid, TransactionException
import time
import asyncio
import hashlib


class TransactionBatcherServer(AsyncInbox):
    def __init__(self, socket_id, wallet, ctx, linger=2000, poll_timeout=500):
        self.block_aggregator_is_ready = False

        self.sent_input_hashes = []
        self.num_mismatches = 0

        super().__init__(socket_id, wallet, ctx, linger, poll_timeout)

    async def send_ack(self, _id):
        await self.return_msg(_id, Message.get_message(MessageType.ACKNOWLEDGED, timestamp=int(time.time())))

    async def handle_msg(self, _id, msg):
        msg_type, msg, sender, timestamp, is_verified = Message.unpack_message_2(message=msg)

        asyncio.ensure_future(self.send_ack(_id))

        if msg_type == MessageType.BURN_INPUT_HASHES:
            self.update_sent_input_hashes(msg.inputHashes)

        elif msg_type == MessageType.READY:
            self.block_aggregator_is_ready = True

    def update_sent_input_hashes(self, input_hashes):
        is_match = False
        for input_hash in input_hashes:
            if input_hash in self.sent_input_hashes:
                oldest_sent_input_hash = self.sent_input_hashes.pop(0)

                while oldest_sent_input_hash != input_hash:
                    oldest_sent_input_hash = self.sent_input_hashes.pop(0)

                is_match = True

        if is_match:
            self.num_mismatches = 0

        else:
            self.num_mismatches += 1


class RateLimiter:
    def __init__(self, block_heartbeat_interval,
                 input_bag_timeout,
                 max_transactions_per_subblock,
                 max_transaction_submission_delay,
                 batcher_sleep_interval):

        self.max_transactions_per_subblock = max_transactions_per_subblock
        self.max_transaction_submission_delay = max_transaction_submission_delay
        self.batcher_sleep_interval = batcher_sleep_interval

        self.current_transaction_delay = 0
        self.empty_bag_delay = 0
        self.max_empty_bag_delay = block_heartbeat_interval - input_bag_timeout

        assert self.max_empty_bag_delay > 0, 'Input bag timeout has to be less than Block heartbeat timeout!'

    def should_sleep(self, transactions_enqueue, bags_sent):
        return bags_sent > 3 or (bags_sent > 0 and transactions_enqueue < self.max_transactions_per_subblock and
                                 self.current_transaction_delay < self.max_transaction_submission_delay and
                                 self.empty_bag_delay < self.max_empty_bag_delay)

    def update_delay_variables_if_needed(self, transactions_enqueue, bags_sent):
        if transactions_enqueue == 0:
            self.empty_bag_delay = self.empty_bag_delay + 1 if bags_sent == 1 else 0
        elif transactions_enqueue < self.max_transactions_per_subblock:
            self.current_transaction_delay += 1

    def get_next_bag_size_and_reset_delays(self, transactions_enqueue):
        bag_size = 0

        if transactions_enqueue >= self.max_transactions_per_subblock or \
                self.current_transaction_delay >= self.max_transaction_submission_delay:

            bag_size = min(transactions_enqueue, self.max_transactions_per_subblock)
            self.current_transaction_delay = 0
        else:
            self.empty_bag_delay = 0

        return bag_size


class TransactionBatcher:
    def __init__(self, socket_id, wallet, ctx, tx_queue, block_aggregator_socket_id, nonce_manager):
        self.wallet = wallet
        self.nonce_manager = nonce_manager
        self.server = TransactionBatcherServer(socket_id=socket_id, wallet=wallet, ctx=ctx)
        self.tx_queue = tx_queue
        self.block_aggregator_socket_id = block_aggregator_socket_id

        self.empty_bag_delay = 0

    def prepare_batch(self, tx_batch: list, hasher):
        # Get a transaction from the queue

        for tx in tx_batch:

            # Make sure that the transaction is valid
            # this is better done at webserver level before packing and putting it into the queue - raghu todo
            try:
                transaction_is_valid(tx=tx,
                                     expected_processor=self.wallet.verifying_key(),
                                     driver=self.nonce_manager,
                                     strict=True)
            except TransactionException:
                tx_batch.remove(tx)

            # Hash it
            tx_bytes = tx.as_builder().to_bytes_packed()
            hasher.update(tx_bytes)

        timestamp = time.time()
        hasher.update('{}'.format(timestamp).encode())
        input_hash = hasher.digest()

        # Sign the message for verification
        signature = self.wallet.sign(input_hash)

        return tx_batch, timestamp, signature, input_hash



    async def process_transactions(self):
        while not self.server.block_aggregator_is_ready:
            await asyncio.sleep(0)
        encoded_filter = TRANSACTION_FILTER.encode()
        cur_txn_delay = 0
        empty_bag_delay = 0
        max_empty_bag_delay = BLOCK_HEART_BEAT_INTERVAL - INPUT_BAG_TIMEOUT
        my_wallet = Wallet(seed=self.signing_key)

        while True:
            num_txns = self.queue.qsize()
            num_bags_sent = self._get_num_bags_sent()

            if (num_txns == 0):
                empty_bag_delay = (empty_bag_delay + 1) if num_bags_sent == 1 \
                    else 0
            elif (num_txns < MAX_TXNS_PER_SUB_BLOCK):
                cur_txn_delay += 1

            if ((num_bags_sent > 3) or \
                    ((num_bags_sent > 0) and (num_txns < MAX_TXNS_PER_SUB_BLOCK) \
                     and (cur_txn_delay < MAX_TXN_SUBMISSION_DELAY) \
                     and (empty_bag_delay < max_empty_bag_delay))):
                await asyncio.sleep(BATCHER_SLEEP_INTERVAL)
                continue

            if (num_txns >= MAX_TXNS_PER_SUB_BLOCK) or \
                    (cur_txn_delay >= MAX_TXN_SUBMISSION_DELAY):
                bag_size = min(num_txns, MAX_TXNS_PER_SUB_BLOCK)
                cur_txn_delay = 0
            else:
                bag_size = 0
                empty_bag_delay = 0

            tx_list = []

            h = hashlib.sha3_256()

            for _ in range(bag_size):
                # Get a transaction from the queue
                tx = self.queue.get()

                # Make sure that the transaction is valid
                # this is better done at webserver level before packing and putting it into the queue - raghu todo
                try:
                    transaction_is_valid(tx=tx[1],
                                         expected_processor=self.wallet.verifying_key(),
                                         driver=self.driver,
                                         strict=True)
                except TransactionException:
                    continue

                # Hash it
                tx_bytes = tx[1].as_builder().to_bytes_packed()
                h.update(tx_bytes)

                # Deserialize it and put it in the list
                tx_list.append(tx[1])

            # Add a timestamp
            timestamp = time.time()
            h.update('{}'.format(timestamp).encode())
            inputHash = h.digest()

            # Sign the message for verification
            signature = my_wallet.sign(inputHash)

            self.sent_input_hashes.append(inputHash)

            mtype, msg = Message.get_message_packed(
                MessageType.TRANSACTION_BATCH,
                transactions=[t for t in tx_list], timestamp=timestamp,
                signature=signature, inputHash=inputHash,
                sender=my_wallet.vk.encode())

            self.pub_sock.send_msg(msg=msg, msg_type=mtype,
                                   filter=TRANSACTION_FILTER.encode())

            self.log.debug1("Send {} / {} transactions with hash {} and timestamp {}"
                            .format(bag_size, len(tx_list), inputHash.hex(), timestamp))

