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

from cilantro_ee.protocol.multiprocessing.worker import Worker

from cilantro_ee.utils.lprocess import LProcess
from cilantro_ee.utils.utils import int_to_bytes, bytes_to_int

from cilantro_ee.constants.system_config import *
from cilantro_ee.constants.zmq_filters import DEFAULT_FILTER, NEW_BLK_NOTIF_FILTER
from cilantro_ee.constants.ports import *

from cilantro_ee.messages.envelope.envelope import Envelope
from cilantro_ee.messages.block_data.block_metadata import NewBlockNotification, SkipBlockNotification, BlockMetaData
from cilantro_ee.messages.consensus.sub_block_contender import SubBlockContender
from cilantro_ee.messages.consensus.align_input_hash import AlignInputHash
from cilantro_ee.messages.signals.delegate import MakeNextBlock, PendingTransactions, NoTransactions
from cilantro_ee.messages.signals.node import Ready
from cilantro_ee.messages.block_data.state_update import *

from cilantro_ee.contracts.sync import sync_genesis_contracts

import asyncio, zmq, os, time, random


IPC_IP = 'block-manager-ipc-sock'
IPC_PORT = 6967


class DBState:
    CATCHUP = 'in_catchup_phase'
    CURRENT = 'up_to_date'

    """ convenience struct to maintain db snapshot state data in one place """
    def __init__(self):
        self.driver = MetaDataStorage()
        self.cur_block_hash = self.driver.get_latest_block_hash()
        self.cur_block_num = self.driver.get_latest_block_num()
        self.my_new_block_hash = None
        self.new_block_hash = None
        self.catchup_mgr = None
        self.num_empty_sbc = 0
        self.num_skip_block = 0
        self.num_fail_block = 0
        self.is_new_block = False
        self.is_catchup_done = False
        # self.state = DBState.CATCHUP
        self.next_block = {}
        self.sub_block_hash_map = {}
        self.input_hash_map = {}

    def reset(self):
        # reset all the state info
        self.my_new_block_hash = None
        self.new_block_hash = None
        self.num_empty_sbc = 0
        self.num_skip_block = 0
        self.num_fail_block = 0
        self.is_new_block = False
        self.next_block.clear()
        self.sub_block_hash_map.clear()
        self.input_hash_map.clear()


class BlockManager(Worker):

    def __init__(self, ip, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = get_logger("BlockManager[{}]".format(self.verifying_key[:8]))

        self.ip = ip
        self.sb_builders = {}  # index -> process
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
        msg = MessageBase.registry[msg_type].from_bytes(msg_blob)
        self.log.debugv("BlockManager received an IPC message from sbb_index {} with message {}".format(sbb_index, msg))

        if isinstance(msg, SubBlockContender):
            self._handle_sbc(msg)
            if msg.is_empty:
                self._reset_sb_have_data(sbb_index)
            else:
                self._set_sb_have_data(sbb_index)
        elif isinstance(msg, Ready):
            self.set_sbb_ready()
        elif isinstance(msg, PendingTransactions):
            self._set_pending_work(sbb_index)
        elif isinstance(msg, NoTransactions):
            self._reset_pending_work(sbb_index)
        # elif isinstance(msg, SomeOtherType):
        #     self._handle_some_other_type_of_msg(msg)
        else:
            raise Exception("BlockManager got unexpected Message type {} over IPC that it does not know how to handle!"
                            .format(type(msg)))

    def handle_sub_msg(self, frames):
        # TODO filter out duplicate NewBlockNotifications
        # (masters should not be sending more than 1, but we should be sure)

        envelope = Envelope.from_bytes(frames[-1])
        msg = envelope.message
        msg_hash = envelope.message_hash

        if isinstance(msg, NewBlockNotification):
            self.log.important3("BM got NewBlockNotification from sender {} with hash {}".format(envelope.sender, msg.block_hash))
            self.handle_block_notification(msg, True)
        elif isinstance(msg, SkipBlockNotification):
            self.log.important3("BM got SkipBlockNotification from sender {} with hash {}".format(envelope.sender, msg.prev_block_hash))
            self.handle_block_notification(msg, False)
        elif isinstance(msg, FailedBlockNotification):
            self.log.important3("BM got FailedBlockNotification from sender {} with hash {}".format(envelope.sender, msg.prev_block_hash))
            self.handle_fail_block(msg)
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
        self.db_state.cur_block_hash = self.driver.latest_block_hash
        self.db_state.cur_block_num = self.driver.latest_block_num
        if not self.db_state.is_catchup_done:
            self.db_state.is_catchup_done = True
            # self.db_state.cur_block_hash, self.db_state.cur_block_num = StateDriver.get_latest_block_info()
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

    def recv_block_notif(self, block: BlockMetaData):
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

        if isinstance(msg, BlockIndexReply):
            self.recv_block_idx_reply(sender, msg)
        elif isinstance(msg, BlockDataReply):
            self.recv_block_data_reply(msg)
        else:
            raise Exception("BlockManager got message type {} from ROUTER socket that it does not know how to handle"
                            .format(type(msg)))

    def _compute_new_block_hash(self):
        # first sort the sb result hashes based on sub block index
        sorted_sb_hashes = sorted(self.db_state.sub_block_hash_map.keys(),
                                  key=lambda result_hash: self.db_state.sub_block_hash_map[result_hash])

        # TODO remove these
        assert len(sorted_sb_hashes) > 0, "nooooooo\nsorted_sb_hashes={}\nsb_hash_map={}"\
            .format(sorted_sb_hashes, self.db_state.sub_block_hash_map)

        # append prev block hash
        return BlockData.compute_block_hash(sbc_roots=sorted_sb_hashes, prev_block_hash=self.db_state.cur_block_hash)

    def _handle_sbc(self, sbc: SubBlockContender):
        self.log.important("Got SBC with sb-index {}. Sending to Masternodes.".format(sbc.sb_index))
        self.pub.send_msg(sbc, header=DEFAULT_FILTER.encode())
        self.db_state.input_hash_map[sbc.sb_index] = sbc.input_hash
        self.db_state.sub_block_hash_map[sbc.result_hash] = sbc.sb_index
        # if sbc.is_empty:
            # self.db_state.num_empty_sbc = self.db_state.num_empty_sbc + 1
            # if self.db_state.num_empty_sbc == NUM_SB_PER_BLOCK:
                # self.skip_block()
                # return
        num_sb = len(self.db_state.sub_block_hash_map)
        if num_sb == NUM_SB_PER_BLOCK:  # got all sub_block
            # compute my new block hash
            self.db_state.my_new_block_hash = self._compute_new_block_hash()
            self.update_db_if_ready()

    # TODO make this DRY
    def _send_msg_over_ipc(self, sb_index: int, message: MessageBase):
        """
        Convenience method to send a MessageBase instance over IPC router socket to a particular SBB process. Includes a
        frame to identify the type of message
        """
        self.log.spam("Sending msg to sb_index {} with payload {}".format(sb_index, message))
        assert isinstance(message, MessageBase), "Must pass in a MessageBase instance"
        id_frame = str(sb_index).encode()
        message_type = MessageBase.registry[type(message)]  # this is an int (enum) denoting the class of message
        self.ipc_router.send_multipart([id_frame, int_to_bytes(message_type), message.serialize()])

    def send_input_align_msg(self, block: BlockMetaData):
        self.log.info("Sending AlignInputHash message to SBBs")
        for i, sb in enumerate(block.sub_blocks):
            # Note: NUM_SB_BUILDERS may not be same as num sub-blocks per block. For anarchy net, it's same
            #       in that case, it may be beneficial to send in sb_index too
            sbb_idx = sb.index % NUM_SB_BUILDERS
            input_hash = sb.input_hash
            message = AlignInputHash.create(input_hash, sb.index)
            self._send_msg_over_ipc(sb_index=sbb_idx, message=message)

    def update_db(self):
        block = self.db_state.next_block[self.db_state.new_block_hash][0]
        if self.db_state.my_new_block_hash != self.db_state.new_block_hash:    # holy cow - mismatch
            self.log.important("Out-of-Consensus - BlockNotification doesn't match my block!")
            if (self.db_state.num_fail_block >= self.my_quorum):
                self.fail_block_action(block)
                return
            # check input hashes and send align / skip messages using input-hash  - don't start next block
            self.send_input_align_msg(block)
            if self.db_state.is_new_block:
                # need to send block-data to catchup to update
                self.recv_block_notif(block)
            else:
                self.send_updated_db_msg()
            return

        assert self.db_state.new_block_hash == self.db_state.my_new_block_hash, \
            "update_db called but my new block hash {} does not match the new block notification's hash " \
            "hash {}".format(self.db_state.my_new_block_hash, self.db_state.new_block_hash)

        self.log.success2("BlockManager has consensus with BlockNotification!")

        if self.db_state.is_new_block:
            self.db_state.cur_block_hash = self.db_state.new_block_hash
            self.db_state.cur_block_num = block.block_num
            self.log.notice("Setting latest block number to {} and block hash to {}"
                            .format(block.block_num, self.db_state.cur_block_hash))

            self.driver.latest_block_hash = self.db_state.cur_block_hash
            self.driver.latest_block_num = block.block_num

        self.send_updated_db_msg()

    def update_db_if_ready(self):
        if not self.db_state.my_new_block_hash or not self.db_state.new_block_hash:
            return          # both are not ready
        if (self._pending_work_at_sbb == 0) and (self._sub_blocks_have_data == 0):
            time.sleep(40)
        # self.db_state.my_new_block_hash == self.db_state.new_block_hash at this point
        self.update_db()

        # reset all the state info
        self.db_state.reset()

    # update current db state to the new block
    def handle_block_notification(self, block_data: BlockMetaData, is_new_block: bool):
        new_block_hash = block_data.block_hash
        self.log.notice("Got {} block notification {}".format("new" if is_new_block else "empty", block_data))

        if not self.db_state.cur_block_hash:
            self.db_state.cur_block_hash = self.driver.latest_block_hash
            self.db_state.cur_block_num = self.driver.latest_block_num

        if new_block_hash == self.db_state.cur_block_hash:
            self.log.info("New block notification is same as current state. Ignoring.")
            return

        if block_data.block_num < self.db_state.cur_block_num:
            self.log.info("New block notification references block num {} that is less than our curr block num {}. "
                          "Ignoring.".format(block_data.block_num, self.db_state.cur_block_num))
            return

        new_blk_num = self.db_state.cur_block_num + 1
        if (new_blk_num < block_data.block_num):
            self.log.warning("Block Notif prev hash {} does not match current hash {}!"
                             .format(block_data.prev_block_hash, self.db_state.cur_block_hash))
            self.recv_block_notif(block_data)
            return

        count = self.db_state.next_block.get(new_block_hash)[1] + 1 if new_block_hash in self.db_state.next_block else 1
        self.db_state.next_block[new_block_hash] = (block_data, count)
        if count == self.my_quorum:
            self.log.info("New block quorum met!")
            self.db_state.new_block_hash = new_block_hash
            self.db_state.is_new_block = is_new_block
            self.update_db_if_ready()

    def skip_block(self):
        if (self.db_state.num_skip_block < self.my_quorum) or (self.db_state.num_empty_sbc != NUM_SB_PER_BLOCK):
            return

        # reset all the state info
        self.db_state.reset()

        self.send_updated_db_msg()

    # just throw away the current sub-blocks and move forward
    def handle_skip_block(self, skip_block: SkipBlockNotification):
        prev_block_hash = skip_block.prev_block_hash
        self.log.info("Got skip block notification with prev block hash {}...".format(prev_block_hash))

        if not self.db_state.cur_block_hash:
            self.db_state.cur_block_hash = self.driver.latest_block_hash
            self.db_state.cur_block_num = self.driver.latest_block_num

        if skip_block.prev_block_hash != self.db_state.cur_block_hash:
            self.log.warning("Got SkipBlockNotif with prev hash {} that does not match our current hash {}!!!"
                             .format(skip_block.prev_block_hash, self.db_state.cur_block_hash))
            # self.db_state.cur_block_hash = None
            # call catch up again
            # self.db_state.catchup_mgr.run_catchup()
            return
        self.db_state.num_skip_block = self.db_state.num_skip_block + 1
        self.skip_block()

    def fail_block_action(self, block_data: FailedBlockNotification):
        # reset all the state info
        self.db_state.reset()

        for idx in range(NUM_SB_BUILDERS):
            self._send_msg_over_ipc(sb_index=idx, message=block_data)

    # out of consensus at master - make sure input hashes are up to date
    def handle_fail_block(self, block_data: FailedBlockNotification):
        prev_block_hash = block_data.prev_block_hash
        self.log.info("Got fail block notification with prev block hash {}...".format(prev_block_hash))

        if not self.db_state.cur_block_hash:
            self.db_state.cur_block_hash = self.driver.latest_block_hash

        if (prev_block_hash != self.db_state.cur_block_hash):
            # self.db_state.cur_block_hash = None
            self.log.important("DB state is not up to date to prev block hash {}".format(prev_block_hash))
            # self.log.important("DB state is not up to date to block hash {}. Starting catchup process again ...".format(prev_block_hash))
            # call catch up again
            # self.db_state.catchup_mgr.run_catchup()
            # return

        self.db_state.num_fail_block = self.db_state.num_fail_block + 1

        if (self.db_state.num_fail_block < self.my_quorum):
            self.log.important("Don't have quorum yet to handle fail block {}".format(prev_block_hash))
            return

        new_block_hash = -1
        self.db_state.next_block[new_block_hash] = (block_data, 1)
        self.db_state.new_block_hash = new_block_hash

        if (len(self.db_state.input_hash_map) < NUM_SB_PER_BLOCK):
            # add a log that it is not ready yet
            self.log.important("Not ready yet to handle fail block {}".format(prev_block_hash))
            return

        self.fail_block_action(block_data)

    def send_updated_db_msg(self):
        self.log.info("Sending MakeNextBlock message to SBBs")
        message = MakeNextBlock.create()
        for idx in range(NUM_SB_BUILDERS):
            self._send_msg_over_ipc(sb_index=idx, message=message)
