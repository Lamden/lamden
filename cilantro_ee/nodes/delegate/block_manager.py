"""
    BlockManager  (main process of delegate)

    This is the main workhorse for managing inter node communication as well as
    coordinating the interpreting and creation of sub-block contenders that form part of new block.
    It creates sub-block builder processes to manage the parallel execution of different sub-blocks.
    It will also participate in conflict resolution of sub-blocks
    It publishes those sub-blocks to masters so they can assemble the new block contender

    It manages the new block notifications from master and update the db snapshot state
    so sub-block builders can proceed to next block

"""

from cilantro_ee.core.logger.base import get_logger

from cilantro_ee.nodes.catchup import CatchupManager
from cilantro_ee.nodes.delegate.sub_block_builder import SubBlockBuilder

from cilantro_ee.services.storage.state import MetaDataStorage

from cilantro_ee.core.utils.worker import Worker

from cilantro_ee.utils.lprocess import LProcess

from cilantro_ee.constants.system_config import *
from cilantro_ee.constants.zmq_filters import DEFAULT_FILTER, NEW_BLK_NOTIF_FILTER
from cilantro_ee.constants.ports import *
from cilantro_ee.constants import conf

from cilantro_ee.core.messages.message_type import MessageType
from cilantro_ee.core.messages.message import Message

from cilantro_ee.core.crypto.wallet import _verify
from cilantro_ee.contracts.sync import sync_genesis_contracts
import hashlib
import asyncio, zmq, time, random
import os

IPC_IP = 'block-manager-ipc-sock'
IPC_PORT = 6967

from cilantro_ee.core.nonces import NonceManager


# class to keep track of sub-blocks sent over from my sub-block builders
class SubBlocks:
    def __init__(self):
        self.sbs = {}
        self.futures = []

    def reset(self):
        self.sbs = {}
        self.futures = []

    def is_quorum(self):
        return len(self.sbs) == NUM_SB_PER_BLOCK

    def add_sub_block(self, sub_block, fut):
        sb_idx = sub_block.subBlockIdx % NUM_SB_PER_BLOCK

        if sb_idx in self.sbs:
            # todo log it as an issue
            pass

        self.sbs[sb_idx] = sub_block

        self.futures.append(fut)

    def get_sb_hashes_sorted(self):
        sb_hashes = []

        for i in range(NUM_SB_PER_BLOCK):
            sb = self.sbs[i]
            sb_hashes.append(sb.resultHash)

        return sb_hashes

    def get_input_hashes_sorted(self):
        sb_hashes = []
        num_sbs = len(self.sbs)

        for i in range(num_sbs):
            sb = self.sbs[i]
            sb_hashes.append(sb.inputHash.hex())

        return sb_hashes


class NextBlockData:
    def __init__(self, block_notif):
        self.block_notif = block_notif
        is_failed = block_notif.which() == "FailedBlock"
        self.quorum_num = FAILED_BLOCK_NOTIFICATION_QUORUM if is_failed \
                            else BLOCK_NOTIFICATION_QUORUM
        self.is_quorum = False
        self.senders = set()

    # TODO: Deprecate. Not used in project files
    def is_quorum(self):
        return self.is_quorum

    def add_sender(self, sender):
        self.senders.add(sender)

        if not self.is_quorum and (len(self.senders) >= self.quorum_num):
            self.is_quorum = True
            return True

        return False


# Keeps track of block notifications from master
class NextBlock:
    def __init__(self):
        self.next_block_data = {}
        self.quorum_block = None
        self.hard_reset()

    # use this when it has to go to catchup
    def hard_reset(self):
        self.next_block_data = {}     # hash of block num -> block hash -> data
        self.quorum_block = None

    def reset(self, block_num):
        if self.quorum_block:
            bn = self.quorum_block.blockNum
            if bn < block_num and bn in self.next_block_data:
                try:
                    del self.next_block_data[bn] # This can never happen because you are checking for the key prior to deleting
                except KeyError:
                    pass
                    # todo add a debug message - not supposed to happen

        self.quorum_block = None

    def is_quorum(self):
        return self.quorum_block != None

    def get_quorum_block(self):
        return self.quorum_block

    def add_notification(self, block_notif, sender, block_num, block_hash):
        if self.quorum_block and (self.quorum_block.blockNum == block_num):
            # todo - if it is not matching blockhash, may need to audit it
            return False

        if block_num not in self.next_block_data: # default dict?
            self.next_block_data[block_num] = {}
            # todo add time info to implement timeout

        if block_hash not in self.next_block_data[block_num]:
            self.next_block_data[block_num][block_hash] = NextBlockData(block_notif)

        if self.next_block_data[block_num][block_hash].add_sender(sender):
            self.quorum_block = block_notif
            return True

        return False


class DBState:
    CATCHUP = 'in_catchup_phase'
    CURRENT = 'up_to_date'

    """ convenience struct to maintain db snapshot state data in one place """
    def __init__(self):
        self.driver = MetaDataStorage()
        self.next_block = NextBlock()
        self.my_sub_blocks = SubBlocks()

        self.catchup_mgr = None
        self.is_catchup_done = False

    def reset(self):
        # reset all the state info
        self.next_block.reset(self.driver.latest_block_num)
        self.my_sub_blocks.reset()


class BlockManager(Worker):
    def __init__(self, ip, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = get_logger("BlockManager[{}]".format(self.verifying_key[:8]))

        self.ip = ip
        self.sb_builders = {}  # index -> process
        # raghu todo - delete this and remove sb_index related functionality
        self.sb_index = PhoneBook.delegates.index(self.wallet.verifying_key().hex()) % NUM_SB_BUILDERS

        self.sbb_not_ready_count = NUM_SB_BUILDERS

        self.db_state = DBState()
        self.my_quorum = PhoneBook.masternode_quorum_min
        self._pending_work_at_sbb = 0
        self._masternodes_ready = set()
        self.start_sub_blocks = 0

        self._thicc_log()

        # Define Sockets (these get set in build_task_list)
        self.router, self.ipc_router, self.pub, self.sub, self.nbn_sub = None, None, None, None, None

        self.ipc_ip = IPC_IP + '-' + str(os.getpid()) + '-' + str(random.randint(0, 2**32))

        self.driver = MetaDataStorage()
        self.nonce_manager = NonceManager()
        self.run()

    def _thicc_log(self):
        self.log.notice("\nBlockManager initializing with\nvk={vk}\nsubblock_index={sb_index}\n"
                        "num_sub_blocks={num_sb}\nnum_blocks={num_blocks}\nsub_blocks_per_block={sb_per_block}\n"
                        "num_sb_builders={num_sb_builders}\nsub_blocks_per_builder={sb_per_builder}\n"
                        "sub_blocks_per_block_per_builder={sb_per_block_per_builder}\n"
                        .format(vk=self.verifying_key, sb_index=self.sb_index, num_sb=NUM_SUB_BLOCKS,
                                num_blocks=NUM_BLOCKS, sb_per_block=NUM_SB_PER_BLOCK,
                                num_sb_builders=NUM_SB_BUILDERS, sb_per_builder=NUM_SB_PER_BUILDER,
                                sb_per_block_per_builder=NUM_SB_PER_BLOCK_PER_BUILDER))

    def run(self):
        self.build_task_list()
        self.log.info("Block Manager starting...")
        self.start_sbb_procs()

        self.loop.run_until_complete(asyncio.gather(*self.tasks))

    def set_pending_work(self, sbb_index):
        # self.log.info("set pending work {} for sbb {}".format(self._pending_work_at_sbb, sbb_index))
        self._pending_work_at_sbb |= (1 << sbb_index)

    def reset_pending_work(self, sbb_index):
        # self.log.info("reset pending work {} for sbb {}".format(self._pending_work_at_sbb, sbb_index))
        self._pending_work_at_sbb &= ~(1 << sbb_index)

    def is_pending_work(self):
        return self._pending_work_at_sbb > 0

    def build_task_list(self):
        # Create a TCP Router socket for comm with other nodes
        # self.router = self.manager.create_socket(socket_type=zmq.ROUTER, name="BM-Router", secure=True)
        self.router = self.manager.create_socket(
            socket_type=zmq.ROUTER,
            name="BM-Router-{}".format(self.verifying_key[-4:]),
            secure=True,
        )
        # self.router.setsockopt(zmq.ROUTER_MANDATORY, 1)  # FOR DEBUG ONLY
        self.router.setsockopt(zmq.IDENTITY, self.verifying_key.encode())
        self.router.bind(port=DELEGATE_ROUTER_PORT, protocol='tcp', ip=self.ip)
        self.tasks.append(self.router.add_handler(self.handle_router_msg))

        # Create ROUTER socket for bidirectional communication with SBBs over IPC
        self.ipc_router = self.manager.create_socket(socket_type=zmq.ROUTER, name="BM-IPC-Router")
        self.ipc_router.setsockopt(zmq.ROUTER_MANDATORY, 1)  # FOR DEBUG ONLY
        self.ipc_router.bind(port=IPC_PORT, protocol='ipc', ip=self.ipc_ip)
        self.tasks.append(self.ipc_router.add_handler(self.handle_ipc_msg, None, True))

        # Create PUB socket to publish new sub_block_contenders to all masters
        # Falcon - is it secure and has a different pub port ??
        #          do we have a corresponding sub at master that handles this properly ?
        self.pub = self.manager.create_socket(
            socket_type=zmq.PUB,
            name="BM-Pub-{}".format(self.verifying_key[-4:]),
            secure=True,
        )
        self.pub.bind(port=DELEGATE_PUB_PORT, protocol='tcp', ip=self.ip)

        self.pub_replacement = self.zmq_ctx.socket(zmq.PUB)

        self.db_state.catchup_mgr = CatchupManager(verifying_key=self.verifying_key,
                                                   signing_key=self.signing_key,
                                                   pub_socket=self.pub,
                                                   router_socket=self.router,
                                                   store_full_blocks=False)

        # Create SUB socket to
        # 1) listen for subblock contenders from other delegates
        # 2) listen for NewBlockNotifications from masternodes
        self.sub = self.manager.create_socket(
            socket_type=zmq.SUB,
            name="BM-Sub-{}".format(self.verifying_key[-4:]),
            secure=True,
        )
        self.sub.setsockopt(zmq.SUBSCRIBE, DEFAULT_FILTER.encode())
        self.sub.setsockopt(zmq.SUBSCRIBE, NEW_BLK_NOTIF_FILTER.encode())

        self.tasks.append(self.sub.add_handler(self.handle_sub_msg))
        self.tasks.append(self._connect_and_process())

    async def _connect_and_process(self):
        # first make sure, we have overlay server ready
        await self._wait_until_ready()

        # Listen to Masternodes over sub and connect router for catchup communication
        for vk in PhoneBook.masternodes:
            self.sub.connect(vk=vk, port=MN_PUB_PORT)
            self.router.connect(vk=vk, port=MN_ROUTER_PORT)

        # now start the catchup
        await self.catchup_db_state()

    async def catchup_db_state(self):
        # do catch up logic here
        await asyncio.sleep(6)  # so pub/sub connections can complete
        assert self.db_state.catchup_mgr, "Expected catchup_mgr initialized at this point"
        self.log.info("Catching up...")

        # Add genesis contracts to state db if needed
        sync_genesis_contracts()

        self.db_state.catchup_mgr.run_catchup()

    def start_sbb_procs(self):
        for i in range(NUM_SB_BUILDERS):
            self.sb_builders[i] = LProcess(target=SubBlockBuilder, name="SBB_Proc-{}".format(i),
                                           kwargs={"ipc_ip": self.ipc_ip, "ipc_port": IPC_PORT,
                                                   "signing_key": self.signing_key, "ip": self.ip,
                                                   "sbb_index": i})

            self.log.info("Starting SBB #{}".format(i))
            self.sb_builders[i].start()

    async def handle_ipc_msg(self, frames):
        self.log.spam("Got msg over ROUTER IPC from a SBB with frames: {}".format(frames))  # TODO delete this
        assert len(frames) == 3, "Expected 3 frames: (id, msg_type, msg_blob). Got {} instead.".format(frames)

        sbb_index = int(frames[0].decode())
        self.log.info('SBBINDEX {}'.format(sbb_index))
        assert sbb_index in self.sb_builders, "Got IPC message with ID {} that is not in sb_builders {}" \
            .format(sbb_index, self.sb_builders)

        mtype_enc = frames[1]
        msg_blob = frames[2]

        msg_type, msg, sender, timestamp, is_verified = Message.unpack_message(mtype_enc, msg_blob)
        if not is_verified:
            self.log.error("Failed to verify the message of type {} from {} at {}. Ignoring it .."
                          .format(msg_type, sender, timestamp))
            return

        if msg_type == MessageType.READY:
            self.log.info('Ready signal received.')
            self.set_sbb_ready()

        elif msg_type == MessageType.PENDING_TRANSACTIONS:
            self.set_pending_work(sbb_index)

        elif msg_type == MessageType.NO_TRANSACTIONS:
            self.reset_pending_work(sbb_index)

        elif msg_type == MessageType.SUBBLOCK_CONTENDER:
            await self._handle_sbc(sbb_index, msg, mtype_enc, msg_blob)

    def handle_sub_msg(self, frames):
        self.log.success('GOT A SUB MESSAGE ON BLOCK MGR')
        self.log.success(frames)

        # Unpack the frames
        msg_filter, msg_type, msg_blob = frames

        msg_type, msg, sender, timestamp, is_verified = Message.unpack_message(msg_type, msg_blob)
        if not is_verified:
            self.log.error("Failed to verify the message of type {} from {} at {}. Ignoring it .."
                          .format(msg_type, sender, timestamp))
            return

        # Process external ready signals
        if msg_type == MessageType.READY:
            # Only allow signals that are sent within 2000 milliseconds to be validated
            if time.time() - timestamp > 2000:
                return

            self._masternodes_ready.add(sender)
            if len(self._masternodes_ready) == PhoneBook.masternode_quorum_min:
                self.send_start_to_sbb()

        # Process block notification messages
        elif msg_type == MessageType.BLOCK_NOTIFICATION:
            self.log.info('Block notification!!')

            self.log.important3("BM got BlockNotification from sender {} with hash {}".format(sender, msg.blockHash.hex()))

            # Process accordingly
            self.handle_block_notification(frames, msg, sender)

    def is_ready_to_start_sub_blocks(self):
        self.start_sub_blocks += 1
        # raghu - wow - who changed this to hard coded 3?
        return self.start_sub_blocks == 3
        
    def send_start_to_sbb(self):
        self.start_sub_blocks += 1
        if self.start_sub_blocks == 3:
            self.send_updated_db_msg()

    def set_catchup_done(self):
        if not self.db_state.is_catchup_done:
            self.db_state.is_catchup_done = True
            self.send_start_to_sbb()

    def set_sbb_ready(self):
        self.sbb_not_ready_count = self.sbb_not_ready_count - 1
        if self.is_sbb_ready():
            self.send_start_to_sbb()
        # log error if count is below 0

    def is_sbb_ready(self):
        return self.sbb_not_ready_count == 0

    def recv_block_data_reply(self, reply):
        # will it block? otherwise, it may not work
        if self.db_state.catchup_mgr.recv_block_data_reply(reply):
            self.set_catchup_done()

    def recv_block_idx_reply(self, sender, reply):
        # will it block? otherwise, it may not work
        if self.db_state.catchup_mgr.recv_block_idx_reply(sender, reply):
            self.set_catchup_done()

    def recv_block_notif(self, block):
        self.db_state.is_catchup_done = False
        # TODO call run_catchup() if catchup_manager is not already catching up
        if self.db_state.catchup_mgr.recv_new_blk_notif(block):
            self.set_catchup_done()

    def handle_router_msg(self, frames):
        sender, msg_type, msg_blob = frames

        msg_type, msg, signer, timestamp, is_verified = Message.unpack_message(msg_type, msg_blob)
        if not is_verified:
            self.log.error("Failed to verify the message of type {} from {} at {}. Ignoring it .."
                          .format(msg_type, signer, timestamp))
            return

        if msg_type == MessageType.BLOCK_INDEX_REPLY:
            self.recv_block_idx_reply(sender, msg)

        elif msg_type == MessageType.BLOCK_DATA:
            self.recv_block_data_reply(msg)

    def _get_new_block_hash(self):
        if not self.db_state.my_sub_blocks.is_quorum():
            return 0
        # first sort the sb result hashes based on sub block index
        sorted_sb_hashes = self.db_state.my_sub_blocks.get_sb_hashes_sorted()

        # append prev block hash

        driver = MetaDataStorage()

        h = hashlib.sha3_256()

        h.update(driver.latest_block_hash)

        for sb_hash in sorted_sb_hashes:
            h.update(sb_hash)

        return h.digest()

    async def _send_sbc(self, mtype_enc: bytes, msg_blob: bytes):
        wait_time = 0
        while not self.is_pending_work() and wait_time < BLOCK_HEART_BEAT_INTERVAL:
            await asyncio.sleep(1)
            wait_time += 1
        # self.log.info("Waited for {} secs. Sending to Masternodes.".format(wait_time))
        # raghu todo - when BM gets a block notification - it should turn off sleep as well as not send in this pub message
        # first sign the message 
        mtype_sgn, msg_sgn = Message.get_message_signed_internal(
                                  signee=self.wallet.verifying_key(),
                                  sign=self.wallet.sign,
                                  msg_type=mtype_enc, msg=msg_blob)
        self.pub.send_msg(filter=DEFAULT_FILTER.encode(),
                          msg_type=mtype_sgn,
                          msg=msg_sgn)

    async def _handle_sbc(self, sbb_index: int, sbc, mtype_enc: bytes, msg_blob: bytes):
        self.log.important("Got SBC with sb-index {} input-hash {}".format(sbc.subBlockIdx, sbc.inputHash.hex()))
        coro = self._send_sbc(mtype_enc, msg_blob)
        fut = asyncio.ensure_future(coro)
        self.db_state.my_sub_blocks.add_sub_block(sbc, fut)

    # TODO make this DRY
    def _send_msg_over_ipc(self, sb_index: int, msg_type, message):
        """
        Convenience method to send a message over IPC router socket to a particular SBB process. Includes a
        frame to identify the type of message
        """
        self.log.spam("Sending msg to sb_index {} with payload {}".format(sb_index, message))

        id_frame = str(sb_index).encode()
        self.ipc_router.send_multipart([id_frame, msg_type, message])

    def _send_fail_block_msg(self, frames):
        for idx in range(NUM_SB_BUILDERS):
            # SIGNAL
            self._send_msg_over_ipc(sb_index=idx, msg_type=frames[1], message=frames[2])

    # make sure block aggregator adds block_num for all notifications?
    def handle_block_notification(self, frames, block, sender: bytes):

        self.log.notice('BM with sender {} being handled'.format(sender))
        self.log.notice("Got block notification for block num {} with hash {}".format(block.blockNum, block.blockHash))

        next_block_num = self.db_state.driver.latest_block_num + 1

        if block.blockNum < next_block_num:
            self.log.info("New block notification with block num {} that is less than or equal to our curr block num {}. "
                          "Ignoring.".format(block.blockNum, self.db_state.driver.latest_block_num))
            return

        if block.blockNum > next_block_num:
            self.log.warning("Current block num {} is behind the block num {} received. Need to run catchup!"
                             .format(self.db_state.driver.latest_block_num, block.blockNum))
            # raghu todo call this below only if it is a new_block_notifi
            self.recv_block_notif(block)     # raghu todo
            return

        is_quorum_met = self.db_state.next_block.add_notification(block, sender, block.blockNum, block.blockHash)

        if is_quorum_met:
            self.log.info("New block quorum met!")
            my_new_block_hash = self._get_new_block_hash()

            self.log.info('New hash {}, recieved hash {}'.format(my_new_block_hash, block.blockHash.hex()))

            if my_new_block_hash == block.blockHash:
                if block.which() == "newBlock":
                    self.db_state.driver.latest_block_num = block.blockNum
                    self.db_state.driver.latest_block_hash = my_new_block_hash

                    # Set the epoch hash if a new epoch has begun
                    if block.blockNum % conf.EPOCH_INTERVAL == 0:
                        self.db_state.driver.latest_epoch_hash = my_new_block_hash

                self.send_updated_db_msg()
                self.nonce_manager.commit_nonces()

                # raghu todo - need to add bgsave for leveldb / redis / ledis if needed here
            else:
                self.log.critical(
                    'BlockNotification hash received is not the same as the one we have!!!\n{}\n{}'.format(
                        my_new_block_hash, block.blockHash))

                # simply forward the block notification. it is input align on sbb
                self._send_fail_block_msg(frames)
                # this can be at sub-block blder level - where it will wait for anothr message only if it is new-block-notif otherwise, it will align input hashes and proceed to make next block
                if block.which() == "newBlock":
                    self.db_state.reset()
                    self.recv_block_notif(block)
                else:
                    self.send_updated_db_msg()

    def send_updated_db_msg(self):
        # first reset my state
        self.db_state.reset()
        self.log.info("Sending MakeNextBlock message to SBBs")

        msg_type, message = Message.get_message_packed(MessageType.MAKE_NEXT_BLOCK)
        for idx in range(NUM_SB_BUILDERS):
            self.ipc_router.send_multipart([str(idx).encode(), msg_type, message])
