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

from cilantro_ee.logger.base import get_logger

from cilantro_ee.nodes.catchup import CatchupManager
from cilantro_ee.nodes.delegate.sub_block_builder import SubBlockBuilder

from cilantro_ee.storage.state import MetaDataStorage

from cilantro_ee.storage.driver import SafeDriver
from cilantro_ee.storage.vkbook import PhoneBook
from cilantro_ee.protocol.multiprocessing.worker import Worker

from cilantro_ee.utils.lprocess import LProcess
from cilantro_ee.utils.utils import int_to_bytes, bytes_to_int

from cilantro_ee.constants.system_config import *
from cilantro_ee.constants.zmq_filters import DEFAULT_FILTER, NEW_BLK_NOTIF_FILTER
from cilantro_ee.constants.ports import *

from cilantro_ee.messages.block_data.block_data import BlockData
from cilantro_ee.messages.base.base import MessageBase
from cilantro_ee.messages.base import base
from cilantro_ee.messages.envelope.envelope import Envelope
from cilantro_ee.messages.block_data.state_update import *
from cilantro_ee.messages.block_data.notification import BlockNotification, NewBlockNotification, SkipBlockNotification, FailedBlockNotification
from cilantro_ee.messages.consensus.sub_block_contender import SubBlockContender
from cilantro_ee.messages.consensus.align_input_hash import AlignInputHash
from cilantro_ee.messages.signals.delegate import MakeNextBlock, PendingTransactions, NoTransactions

from cilantro_ee.messages.signals.node import Ready
from cilantro_ee.messages.block_data.state_update import *

from cilantro_ee.contracts.sync import sync_genesis_contracts

import asyncio, zmq, os, time, random
from collections import defaultdict
from typing import List


IPC_IP = 'block-manager-ipc-sock'
IPC_PORT = 6967


# class to keep track of sub-blocks sent over from my sub-block builders
class SubBlocks:
    def __init__(self):
        self.sbs = {}

    def reset(self):
        self.sbs = {}

    def is_quorum(self):
        return len(self.sbs) == NUM_SB_BUILDERS

    def add_sub_block(self, sb_index, sub_block):
        if sb_index in self.sbs:
            # todo log it as an issue
            pass
        self.sbs[sb_index] = sub_block

    def get_sb_hashes_sorted(self):
        sb_hashes = []
        for i in range(NUM_SB_BUILDERS):
            sb = self.sbs[i]
            sb_hashes.append(sb.result_hash)
        return sb_hashes


class NextBlockData:
    def __init__(self, block_notif):
        self.block_notif = block_notif
        is_failed = isinstance(block_notif, FailedBlockNotification)
        self.quorum_num = FAILED_BLOCK_NOTIFICATION_QUORUM if is_failed \
                            else BLOCK_NOTIFICATION_QUORUM
        self.is_quorum = False
        self.senders = set()

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
        self.hard_reset()

    # use this when it has to go to catchup
    def hard_reset(self):
        self.next_block_data = {}     # hash of block num -> block hash -> data
        self.quorum_block = None

    def reset(self, block_num):
        if self.quorum_block:
            bn = self.quorum_block.block_num
            if bn < block_num and bn in self.next_block_data:
                try:
                    del self.next_block_data[bn]
                except KeyError:
                    pass
                    # todo add a debug message - not supposed to happen
        self.quorum_block = None

    def is_quorum(self):
        return self.quorum_block != None

    def get_quorum_block(self):
        return self.quorum_block

    def add_notification(self, block_notif, sender):
        bn = block_notif.block_num
        if self.quorum_block and (self.quorum_block.block_num == bn):
            # todo - if it is not matching blockhash, may need to audit it
            return False
        if bn not in self.next_block_data:
            self.next_block_data[bn] = {}
            # todo add time info to implement timeout
        bh = block_notif.block_hash
        if bh not in self.next_block_data[bn]:
            self.next_block_data[bn][bh] = NextBlockData(block_notif)
        if self.next_block_data[bn][bh].add_sender(sender):
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
        self.sb_index = self._get_my_index() % NUM_SB_BUILDERS
        self.sbb_not_ready_count = NUM_SB_BUILDERS

        self.db_state = DBState()
        self.my_quorum = PhoneBook.masternode_quorum_min
        self._pending_work_at_sbb = 0
        self._sub_blocks_have_data = 0
        self._masternodes_ready = set()
        self.start_sub_blocks = 0

        self._thicc_log()

        # Define Sockets (these get set in build_task_list)
        self.router, self.ipc_router, self.pub, self.sub = None, None, None, None

        self.ipc_ip = IPC_IP + '-' + str(os.getpid()) + '-' + str(random.randint(0, 2**32))

        self.driver = MetaDataStorage()
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

    def _add_masternode_ready(self, mn_vk):
        if mn_vk in self._masternodes_ready:
            return
        self._masternodes_ready.add(mn_vk)
        if self._are_masternodes_ready():
            self.send_start_to_sbb()

    def _is_pending_work(self):
        return self._pending_work_at_sbb > 0

    # raghu todo need bit maps here
    def _are_masternodes_ready(self):
        return len(self._masternodes_ready) == self.my_quorum

    def _set_pending_work(self, sbb_index):
        self._pending_work_at_sbb |= (1 << sbb_index)

    def _reset_pending_work(self, sbb_index):
        self._pending_work_at_sbb &= ~(1 << sbb_index)

    def _set_sb_have_data(self, sbb_index):
        self._sub_blocks_have_data |= (1 << sbb_index)

    def _reset_sb_have_data(self, sbb_index):
        self._sub_blocks_have_data &= ~(1 << sbb_index)

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
        self.tasks.append(self.ipc_router.add_handler(self.handle_ipc_msg))

        # Create PUB socket to publish new sub_block_contenders to all masters
        # Falcon - is it secure and has a different pub port ??
        #          do we have a corresponding sub at master that handles this properly ?
        self.pub = self.manager.create_socket(
            socket_type=zmq.PUB,
            name="BM-Pub-{}".format(self.verifying_key[-4:]),
            secure=True,
        )
        self.pub.bind(port=DELEGATE_PUB_PORT, protocol='tcp', ip=self.ip)

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

    def _connect_master_node(self, vk):
        self.sub.connect(vk=vk, port=MN_PUB_PORT)
        self.router.connect(vk=vk, port=MN_ROUTER_PORT)

    async def _connect_and_process(self):
        # first make sure, we have overlay server ready
        await self._wait_until_ready()

        # Listen to Masternodes over sub and connect router for catchup communication
        for vk in PhoneBook.masternodes:
            self._connect_master_node(vk)

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

    def _get_my_index(self):
        for index, vk in enumerate(PhoneBook.delegates):
            if vk == self.verifying_key:
                return index

        raise Exception("Delegate VK {} not found in VKBook {}".format(self.verifying_key, PhoneBook.delegates))

    def handle_ipc_msg(self, frames):
        self.log.spam("Got msg over ROUTER IPC from a SBB with frames: {}".format(frames))  # TODO delete this
        assert len(frames) == 3, "Expected 3 frames: (id, msg_type, msg_blob). Got {} instead.".format(frames)

        sbb_index = int(frames[0].decode())
        assert sbb_index in self.sb_builders, "Got IPC message with ID {} that is not in sb_builders {}" \
            .format(sbb_index, self.sb_builders)

        msg_type = bytes_to_int(frames[1])
        msg_blob = frames[2]

        if MessageBase.registry.get(msg_type) is not None:
            msg = MessageBase.registry[msg_type].from_bytes(msg_blob)

        elif base.SIGNALS.get(msg_type):
            msg = base.SIGNALS.get(msg_type)

        self.log.debugv("BlockManager received an IPC message from sbb_index {} with message {}".format(sbb_index, msg))

        if isinstance(msg, MessageBase):
            # DATA
            if isinstance(msg, SubBlockContender):
                self._handle_sbc(sbb_index, msg)
                if msg.is_empty:
                    self._reset_sb_have_data(sbb_index)
                else:
                    self._set_sb_have_data(sbb_index)

            # SIGNAL
            elif isinstance(msg, Ready):
                self.set_sbb_ready()

            # SIGNAL
            elif isinstance(msg, PendingTransactions):
                self._set_pending_work(sbb_index)

            # SIGNAL
            elif isinstance(msg, NoTransactions):
                self._reset_pending_work(sbb_index)

            else:
                raise Exception("BlockManager got unexpected Message type {} over IPC that it does not know how to handle!"
                                .format(type(msg)))

        elif isinstance(msg, base.Signal):
            # SIGNAL
            if isinstance(msg, base.Ready):
                self.set_sbb_ready()

            # SIGNAL
            elif isinstance(msg, base.PendingTransactions):
                self._set_pending_work(sbb_index)

            # SIGNAL
            elif isinstance(msg, base.NoTransactions):
                self._reset_pending_work(sbb_index)

    def handle_sub_msg(self, frames):
        envelope = Envelope.from_bytes(frames[-1])
        msg = envelope.message
        sender = envelope.sender

        if isinstance(msg, BlockNotification):
            self.log.important3("BM got BlockNotification from sender {} with hash {}".format(envelope.sender, msg.block_hash))
            self.handle_block_notification(msg, sender)
        elif isinstance(msg, Ready):
            self._add_masternode_ready(envelope.sender)
        else:
            raise Exception("BlockManager got message type {} from SUB socket that it does not know how to handle"
                            .format(type(msg)))


    def is_ready_to_start_sub_blocks(self):
        self.start_sub_blocks += 1
        return self.start_sub_blocks == 3
        
    def send_start_to_sbb(self):
        if self.is_ready_to_start_sub_blocks():
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

    def recv_block_notif(self, block: BlockNotification):
        self.db_state.is_catchup_done = False
        # TODO call run_catchup() if catchup_manager is not already catching up
        if self.db_state.catchup_mgr.recv_new_blk_notif(block):
            self.set_catchup_done()

    def handle_router_msg(self, frames):
        envelope = Envelope.from_bytes(frames[-1])
        sender = envelope.sender
        assert sender.encode() == frames[0], "Sender vk {} does not match id frame {}".format(sender.encode(), frames[0])
        msg = envelope.message
        msg_hash = envelope.message_hash

        # DATA
        if isinstance(msg, BlockIndexReply):
            self.recv_block_idx_reply(sender, msg)

        # DATA
        elif isinstance(msg, BlockDataReply):
            self.recv_block_data_reply(msg)
        else:
            raise Exception("BlockManager got message type {} from ROUTER socket that it does not know how to handle"
                            .format(type(msg)))

    def _get_new_block_hash(self):
        if not self.db_state.my_sub_blocks.is_quorum():
            return 0
        # first sort the sb result hashes based on sub block index
        sorted_sb_hashes = self.db_state.my_sub_blocks.get_sb_hashes_sorted()

        # append prev block hash
        return BlockData.compute_block_hash(sbc_roots=sorted_sb_hashes, prev_block_hash=self.db_state.driver.latest_block_hash)

    def _handle_sbc(self, sbb_index: int, sbc: SubBlockContender):
        self.log.important("Got SBC with sb-index {} result-hash {}. Sending to Masternodes.".format(sbc.sb_index, sbc.result_hash))
        # if not self._is_pending_work() and (sbb_index == 0): # todo need async methods here
        self.pub.send_msg(sbc, header=DEFAULT_FILTER.encode())
        self.db_state.my_sub_blocks.add_sub_block(sbb_index, sbc)

    # TODO make this DRY
    def _send_msg_over_ipc(self, sb_index: int, message):
        """
        Convenience method to send a MessageBase instance over IPC router socket to a particular SBB process. Includes a
        frame to identify the type of message
        """
        self.log.spam("Sending msg to sb_index {} with payload {}".format(sb_index, message))

        if isinstance(message, MessageBase):
            id_frame = str(sb_index).encode()
            message_type = MessageBase.registry[type(message)]  # this is an int (enum) denoting the class of message
            self.ipc_router.send_multipart([id_frame, int_to_bytes(message_type), message.serialize()])

        elif isinstance(message, base.Signal):
            id_frame = str(sb_index).encode()
            signal_type = base.SIGNAL_VALUES[type(message)]
            self.log.spam("Message being sent via signal {}".format([id_frame, int_to_bytes(signal_type), b'']))
            self.ipc_router.send_multipart([id_frame, int_to_bytes(signal_type), b''])

    def _send_input_align_msg(self, block: BlockNotification):
        self.log.info("Sending AlignInputHash message to SBBs")
        first_sb_index = block.first_sb_index
        for i, input_hash in enumerate(block.input_hashes):
            # DATA
            message = AlignInputHash.create(input_hash, first_sb_index + i)
            sb_idx = i % NUM_SB_BUILDERS
            self._send_msg_over_ipc(sb_index=sb_idx, message=message)

    def _send_fail_block_msg(self, block_data: FailedBlockNotification):
        for idx in range(NUM_SB_BUILDERS):
            # SIGNAL
            self._send_msg_over_ipc(sb_index=idx, message=block_data)


    def update_db_state(self, block_notif: BlockNotification):
        my_new_block_hash = self._get_new_block_hash()
        if my_new_block_hash == block_notif.block_hash:
            if isinstance(block_notif, NewBlockNotification):
                self.db_state.driver.latest_block_num = block_notif.block_num
                self.db_state.driver.latest_block_hash = my_new_block_hash
            self.send_updated_db_msg()
            # raghu todo - need to add bgsave for leveldb / redis / ledis if needed here
        else:
            if isinstance(block_notif, FailedBlockNotification):
                self._send_fail_block_msg(block_notif)
            else:
                self._send_input_align_msg(block_notif)
            if isinstance(block_notif, NewBlockNotification):
                self.recv_block_notif(block_notif)
            else:
                self.send_updated_db_msg()


    # make sure block aggregator adds block_num for all notifications?
    def handle_block_notification(self, block_notif: BlockNotification, sender: str):
        new_block_num = block_notif.block_num
        self.log.notice("Got block notification for block num {} hash {}".format(new_block_num, block_notif.block_hash))

        next_block_num = self.db_state.driver.latest_block_num + 1

        if new_block_num < next_block_num:
            self.log.info("New block notification with block num {} that is less than or equal to our curr block num {}. "
                          "Ignoring.".format(new_block_num, self.db_state.driver.latest_block_num))
            return

        if (new_block_num > next_block_num):
            self.log.warning("Current block num {} is behind the block num {} received. Need to run catchup!"
                             .format(self.db_state.driver.latest_block_num, new_block_num))
            self.recv_block_notif(block_notif)     # raghu todo
            return

        is_quorum_met = self.db_state.next_block.add_notification(block_notif, sender)
        if is_quorum_met:
            self.log.info("New block quorum met!")
            self.update_db_state(block_notif)

    def send_updated_db_msg(self):
        # first reset my state
        self.db_state.reset()
        self.log.info("Sending MakeNextBlock message to SBBs")

        # SIGNAL
        #message = MakeNextBlock.create()
        message = base.MakeNextBlock()
        for idx in range(NUM_SB_BUILDERS):
            self._send_msg_over_ipc(sb_index=idx, message=message)
