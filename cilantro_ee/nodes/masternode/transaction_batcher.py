from cilantro_ee.constants.zmq_filters import TRANSACTION_FILTER
from cilantro_ee.constants.ports import MN_TX_PUB_PORT
from cilantro_ee.constants.batcher import BATCHER_SLEEP_INTERVAL
from cilantro_ee.constants.batcher import MAX_TXN_SUBMISSION_DELAY
from cilantro_ee.constants.batcher import MAX_TXNS_PER_SUB_BLOCK
from cilantro_ee.constants.system_config import BLOCK_HEART_BEAT_INTERVAL
from cilantro_ee.constants.system_config import INPUT_BAG_TIMEOUT
from cilantro_ee.protocol.multiprocessing.worker import Worker
import zmq.asyncio
import asyncio, time
import hashlib
from cilantro_ee.core.messages.message_type import MessageType
from cilantro_ee.core.messages.message import Message
from cilantro_ee.protocol.wallet import Wallet, _verify
from cilantro_ee.protocol.pow import SHA3POWBytes
from cilantro_ee.protocol.transaction import transaction_is_valid
from cilantro_ee.storage.state import MetaDataStorage
from contracting import config


class TransactionBatcher(Worker):

    def __init__(self, queue, ip, ipc_ip, ipc_port, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue, self.ip = queue, ip
        self.ipc_ip = ipc_ip
        self.ipc_port = ipc_port
        self._ready = False

        self.driver = MetaDataStorage()

        # Create Pub socket to broadcast to witnesses
        self.pub_sock = self.manager.create_socket(socket_type=zmq.PUB, name="TxBatcher-PUB", secure=True)
        self.pub_sock.bind(port=MN_TX_PUB_PORT, ip=self.ip)

        # Create DEALER socket to talk to the BlockManager process over IPC
        self.ipc_dealer = None
        self._create_dealer_ipc(port=ipc_port, ip=ipc_ip, identity=str(0).encode())

        self.sent_input_hashes = []
        self.num_mismatches = 0

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
                        "ip {}, port {}".format(self.ipc_ip, self.ipc_port))
        self.ipc_dealer.connect(port=self.ipc_port, protocol='ipc', ip=self.ipc_ip)

    def _get_num_bags_sent(self):
        return len(self.sent_input_hashes) - self.num_mismatches

    def _update_sent_input_hashes(self, input_hashes):
        qsz = len(self.sent_input_hashes)
        is_match = False
        for input_hash in input_hashes:
            if input_hash in self.sent_input_hashes:
                ih = self.sent_input_hashes.pop(0)
                while ih != input_hash:
                    ih = self.sent_input_hashes.pop(0)
                is_match = True
        if is_match:
            self.num_mismatches = 0
        else:
            self.num_mismatches += 1

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
            self._update_sent_input_hashes(msg.inputHashes)

        elif msg_type == MessageType.READY:
            self.log.success('READY.')
            self._ready = True

        else:
            self.log.error("Batcher got unexpected message type {} from BA's IPC "
                           "socket. Ignoring the msg {}".format(type(msg), msg))

    async def _wait_until_ready(self):
        await asyncio.sleep(1)
        self._connect_dealer_ipc()
        while not self._ready:
            await asyncio.sleep(1)

    async def compose_transactions(self):
        await self._wait_until_ready()

        self.log.notice("Starting TransactionBatcher ...")
        self.log.debugv("Current queue size is {}".format(self.queue.qsize()))

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
                bag_size =  min(num_txns, MAX_TXNS_PER_SUB_BLOCK)
                cur_txn_delay = 0
            else:
                bag_size =  0
                empty_bag_delay = 0

            tx_list = []

            h = hashlib.sha3_256()

            for _ in range(bag_size):
                # Get a transaction from the queue
                tx = self.queue.get()

                # Make sure that the transaction is valid
                # this is better done at webserver level before packing and putting it into the queue - raghu todo
                if not transaction_is_valid(tx=tx,
                                            expected_processor=self.wallet.verifying_key(),
                                            driver=self.driver,
                                            strict=True):
                    continue

                # Hash it
                tx_bytes = tx.as_builder().to_bytes_packed()
                h.update(tx_bytes)

                # Deserialize it and put it in the list
                tx_list.append(tx)

            # Add a timestamp
            timestamp = time.time()
            h.update('{}'.format(timestamp).encode())
            inputHash = h.digest()

            # Sign the message for verification
            signature = my_wallet.sign(inputHash)

            self.sent_input_hashes.append(inputHash)

            mtype, msg = Message.get_message_packed(
                             MessageType.TRANSACTION_BATCH,
                             transactions=tx_list, timestamp=timestamp,
                             signature=signature, inputHash=inputHash,
                             sender=my_wallet.verifying_key())

            self.pub_sock.send_msg(msg=msg, msg_type=mtype,
                                   filter=TRANSACTION_FILTER.encode())


            self.log.debug1("Send {} / {} transactions with hash {} and timestamp {}"
                      .format(bag_size, len(tx_list), inputHash.hex(), timestamp))

