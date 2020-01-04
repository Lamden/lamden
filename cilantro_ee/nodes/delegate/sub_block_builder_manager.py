"""
    SBBuilderManager  (main process of delegate)

    This is the main workhorse for managing inter node communication as well as
    coordinating the sub-block production and block notifications.
    It creates sub-block builder processes to manage the parallel building of different sub-blocks.
    It publishes those sub-blocks to masters so they can assemble the new blocks
       and manages the block notifications arising from that process and the follow up actions.

"""

from cilantro_ee.core.logger import get_logger

from cilantro_ee.core.block_fetch import BlockFetcher
from cilantro_ee.nodes.delegate.sub_block_builder import SubBlockBuilder

from cilantro_ee.services.storage.state import MetaDataStorage

from cilantro_ee.core.utils.worker import Worker

from cilantro_ee.utils.lprocess import LProcess

from cilantro_ee.constants.block import BLOCK_HEART_BEAT_INTERVAL
from cilantro_ee.constants.zmq_filters import DEFAULT_FILTER, NEW_BLK_NOTIF_FILTER
from cilantro_ee.constants.ports import *

from cilantro_ee.messages.message_type import MessageType
from cilantro_ee.messages.message import Message
from cilantro_ee.crypto import BlockSubBlockMapper
from cilantro_ee.services.storage.vkbook import VKBook
from cilantro_ee.contracts import sync
import hashlib
import asyncio, zmq, random
import os


# class to keep track of sub-blocks sent over from my sub-block builders
class SubBlockHandler:
    def __init__(self, num_sb_per_block):
        self.num_sb_per_block = num_sb_per_block
        self.sbs = {}

    def reset(self):
        self.sbs = {}

    def is_quorum(self):
        return len(self.sbs) == self.num_sb_per_block

    def add_sub_block(self, sub_block):
        sbb_idx = BlockSubBlockMapper.get_builder_index(sub_block.subBlockNum,
                                                        self.num_sb_per_block)
        if sbb_idx in self.sbs:
            # todo log it as an issue
            pass
        self.sbs[sbb_idx] = sub_block

    def get_sb_hashes_sorted(self):
        sb_hashes = []
        for i in range(self.num_sb_per_block):
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

    def get_new_block_hash(self, prev_block_hash):
        if not self.is_quorum():
            return 0

        h = hashlib.sha3_256()

        # first add prev block hash
        h.update(prev_block_hash)

        # add all sb result hashes in order
        for i in range(self.num_sb_per_block):
            h.update(self.sbs[i].resultHash)

        # return hash of it
        return h.digest()


class BlockNotifData:
    def __init__(self, block_notif, bn_quorum, fbn_quorum):
        self.block_notif = block_notif
        is_failed = block_notif.which() == "FailedBlock"
        self.quorum_num = fbn_quorum if is_failed else bn_quorum
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
class BlockNotifHandler:
    def __init__(self, num_masters):
        self.hard_reset()
        self.blk_notif_quorum = (num_masters + 1) // 2
        self.failed_blk_notif_quorum = num_masters - self.blk_notif_quorum + 1

    # use this when it has to go to catchup
    def hard_reset(self):
        self.block_notif_data = {}    # hash of block num -> block hash -> data
        self.quorum_block = None

    def reset(self, block_num):
        if self.quorum_block:
            bn = self.quorum_block.blockNum
            if bn < block_num and bn in self.block_notif_data:
                try:
                    del self.block_notif_data[bn]
                except KeyError:
                    pass
                    # todo add a debug message - not supposed to happen
        self.quorum_block = None

    def is_quorum(self):
        return self.quorum_block != None

    def get_quorum_block(self):
        return self.quorum_block

    def add_notification(self, block_notif, sender):
        block_num = block_notif.blockNum
        block_hash = block_notif.blockHash
        if self.quorum_block and (self.quorum_block.blockNum == block_num):
            # todo - if it is not matching blockhash, may need to audit it
            return False

        if block_num not in self.block_notif_data:
            self.block_notif_data[block_num] = {}
            # todo add time info to implement timeout

        if block_hash not in self.block_notif_data[block_num]:
            self.block_notif_data[block_num][block_hash] = \
                   BlockNotifData(block_notif, self.blk_notif_quorum, self.failed_blk_notif_quorum)

        if self.block_notif_data[block_num][block_hash].add_sender(sender):
            self.quorum_block = block_notif
            return True

        return False


class SubBlockManager:
    def __init__(self, wallet, zmq_ctx, log, sb_builder_requests,
                 min_mn_quorum, num_masters, num_sb_builders):
        self.log = log
        self.sbb_requests = sb_builder_requests
        self.num_sb_builders = num_sb_builders
        self.sb_handler = SubBlockHandler(num_sb_builders)
        self.bn_handler = BlockNotifHandler(num_masters)
        self.fetcher = BlockFetcher(wallet=wallet, ctx=zmq_ctx) 
        self.driver = MetaDataStorage()


    def reset(self):
        # reset all the state info
        self.bn_handler.reset(self.driver.latest_block_num)
        self.sb_handler.reset()


    async def start_catchup_process(self):
        self.log.info("Catching up...")

        # Add genesis contracts to state db if needed
        sync.sync_genesis_contracts()

        # start catchup process
        await self.fetcher.sync()
        self.make_next_sb()


    # called only when block-notif is more than one block ahead of state
    async def catchup_block_notif(self, block):
        await self.db_handler.catchup_block_notif(block)



    # todo
    # seems like driver goes with bn-handler, perhaps at manager level which is passing
    # need to move this to blk notif handler
    # make sure block aggregator adds block_num for all notifications?
    async def handle_block_notification(self, block, sender: bytes):

        # todo - convert this to string hex for audit purposes ?
        self.log.notice('BM with sender {} being handled'.format(sender))
        self.log.info("Got block notification for block num {} with hash {}"
                                   .format(block.blockNum, block.blockHash))

        cur_block_num = self.driver.latest_block_num 
        next_block_num = cur_block_num + 1

        if block.blockNum < next_block_num:
            self.log.info("New block notification with block num {} that is "
                          "not more than our curr block num {}. Ignoring .."
                          .format(block.blockNum, cur_block_num))
            return

        is_quorum_met = self.bn_handler.add_notification(block, sender)

        if is_quorum_met:
            self.log.info("New block quorum met!")
            if block.blockNum > next_block_num:
                self.log.warning("Current block (# {}) is behind by more than "
                                 "one block from the received block (# {}). "
                                 "Need to run catchup!"
                                 .format(cur_block_num, block.blockNum))

            my_new_block_hash = self.sb_handler.get_new_block_hash(self.driver.latest_block_hash)
            self.log.info('New hash {}, received hash {}'.format(my_new_block_hash, block.blockHash.hex()))

            if my_new_block_hash == block.blockHash:
                if block.which() == "newBlock":
                    self.driver.latest_block_num = block.blockNum
                    self.driver.latest_block_hash = my_new_block_hash

                # todo - nonce commit is removed. need to fix this
                self.commit_cur_db()

            else:
                self.log.critical(
                    'BlockNotification hash received is not the same as the one we have!!!\n{}\n{}'.format(
                        my_new_block_hash, block.blockHash))

                # simply forward the block notification. it is input align on sbb
                self.discord_cur_db(block.subBlockNum, block.inputHashes)
                if block.which() == "newBlock":
                    self.reset()
                    await self.fetcher.intermediate_sync(block) 
            self.make_next_sb()

    def commit_cur_db(self):
        self.sbb_requests['commit_cur_sb']()


    def discord_cur_db(self, sb_numbers, input_hashes):
        self.sbb_requests['discord_cur_sb_and_align'](sb_numbers, input_hashes)

    def make_next_sb(self):
        self.sbb_requests['make_next_sb']()


class SBBState:
    def __init__(self, num_sb_builders):
        self.num_sb_builders = num_sb_builders
        self.sbb_ready_count = 0

        self.pending_work_at_sbb = 0         # bit map
        
    def set_sbb_ready(self):
        self.sbb_ready_count += 1

    def are_sbbs_ready(self):
        return self.sbb_ready_count == self.num_sb_builders

    def set_pending_work(self, sbb_index):
        self._pending_work_at_sbb |= (1 << sbb_index)

    def set_no_work(self, sbb_index):
        self._pending_work_at_sbb &= ~(1 << sbb_index)

    def is_ready_for_next_sb(self):
        return (self.pending_work_at_sbb > 0)

# start catch up only when these two are true
#               (self.not_met_mn_quorum <= 0) and (self.not_ready_sbb_count <= 0)
class SubBlockBuilderManager(Worker):
    def __init__(self, ip, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = get_logger("SBBuilderManager[{}]".format(self.verifying_key[:8]))

        self.ip = ip
        # todo - choose random open port number for additional security
        # todo - even ipc sockets require zmq handshake
        self.ipc_port = 6967   # hard coded port number right now
        self.ipc_ip =  'sbb-mgr-' + str(os.getpid()) + '-' \
                       + str(random.randint(0, 2**32))

        self.vkbook = VKBook()

        self.mn_quorum_min = self.vkbook.masternode_quorum_min
        self.mn_ready_count = 0
        self.masternodes_ready = set()
        self.masternodes = self.vkbook.masternodes
        num_masters = len(self.masternodes)

        self.sb_mapper = BlockSubBlockMapper(self.masternodes)
        self.sb_builders = {}  # index -> process
        self.sbb_state = SBBState(self.sb_mapper.num_sb_builders)

        # crp todo - pass in self.log or eliminate logging at this level??
        self.sbb_requests = {
                'make_next_sb': self.send_make_next_sb,
                'commit_cur_sb': self.send_commit_cur_sb,
                'discord_cur_sb_and_align': self.send_discord_cur_sb_and_align}

        self.sb_mgr = None

        # Define Sockets (these get set in build_task_list)
        self.router, self.ipc_router, self.pub, self.sub = None, None, None, None


    def start(self):
        self.log.info("Sub-block builder manager starting...")
        self.sync_setup()
        self.loop.run_until_complete(asyncio.gather(*self.tasks))

    def sync_setup(self):
        self.sb_mgr = SubBlockManager(self.wallet, self.zmq_ctx, self.log,
                                      self.sbb_requests, self.mn_quorum_min,
                                      num_masters, self.sb_mapper.num_sb_builders)
        self.create_sockets()
        self.build_task_list()

    def create_sockets(self):
        # Create a TCP Router socket for comm with other nodes
        self.router = self.manager.create_socket(
            socket_type=zmq.ROUTER,
            name="SBBM-Router-{}".format(self.verifying_key[-4:]),
            secure=True,
        )
        # self.router.setsockopt(zmq.ROUTER_MANDATORY, 1)  # FOR DEBUG ONLY
        self.router.setsockopt(zmq.IDENTITY, self.verifying_key.encode())
        self.router.bind(port=DELEGATE_ROUTER_PORT, protocol='tcp', ip=self.ip)

        # Create ROUTER socket for bidirectional communication with SBBs over IPC
        self.ipc_router = self.manager.create_socket(socket_type=zmq.ROUTER,
                                                     name="SBBM-IPC-Router")
        self.ipc_router.setsockopt(zmq.ROUTER_MANDATORY, 1)  # FOR DEBUG ONLY
        self.ipc_router.bind(port=self.ipc_port, protocol='ipc', ip=self.ipc_ip)

        # Create PUB socket to publish new sub_block_contenders to all masters
        self.pub = self.manager.create_socket(
            socket_type=zmq.PUB,
            name="SBBM-Pub-{}".format(self.verifying_key[-4:]),
            secure=True,
        )
        self.pub.bind(port=DELEGATE_PUB_PORT, protocol='tcp', ip=self.ip)


        # Create SUB socket to
        # 1) listen for subblock contenders from other delegates
        # 2) listen for NewBlockNotifications from masternodes
        self.sub = self.manager.create_socket(
            socket_type=zmq.SUB,
            name="SBBM-Sub-{}".format(self.verifying_key[-4:]),
            secure=True,
        )
        self.sub.setsockopt(zmq.SUBSCRIBE, DEFAULT_FILTER.encode())
        self.sub.setsockopt(zmq.SUBSCRIBE, NEW_BLK_NOTIF_FILTER.encode())

    
    def build_task_list(self):
        self.tasks.append(self.router.add_handler(self.handle_router_msg))
        self.tasks.append(self.ipc_router.add_handler(self.handle_ipc_msg, None, True))
        self.tasks.append(self.sub.add_handler(self.handle_sub_msg))
        self.tasks.append(self.async_setup1())
        self.tasks.append(self.async_setup2())

    def set_masternode_ready(self, sender):
        if sender not in self.masternodes_ready:
            self.masternodes_ready.add(sender)
            self.mn_ready_count += 1

    def start_sbb_procs(self, ipc_ip, ipc_port):
        sub_list = self.sb_mapper.get_list_of_subscriber_list()
        kwargs={'signing_key': self.signing_key, 
                'num_sb_builders': self.sb_mapper.num_sb_builders,
                'ipc_ip': ipc_ip, 'ipc_port': ipc_port}

        for i in range(self.sb_mapper.num_sb_builders):
            kwargs['sbb_index'] = i
            kwargs['sub_list'] = sub_list[i]
            self.sb_builders[i] = LProcess(target=SubBlockBuilder,
                                           name="SBB_Proc-{}".format(i),
                                           kwargs=kwargs)

            self.log.info("Starting SBB #{}".format(i))
            self.sb_builders[i].start()

    async def async_setup1(self):
        self.start_sbb_procs(self.ipc_ip, self.ipc_port)

    async def async_setup2(self):
        # first make sure, we have overlay server ready
        await self._wait_until_ready()

        # Listen to Masternodes over sub and connect router for catchup communication
        for vk in self.masternodes:
            self.sub.connect(vk=vk, port=MN_PUB_PORT)
            self.router.connect(vk=vk, port=MN_ROUTER_PORT)

        # need to wait for 6 secs to let connections form as well as
        # sub-block builders and min number of master nodes ready
        wait_time = 0
        while not self.sbb_state.are_sbbs_ready() or \
              ((wait_time < 6) and (self.mn_ready_count < self.mn_quorum_min)): 
            wait_time += 1
            asyncio.sleep(1)

        # now start the catchup
        await self.sb_mgr.start_catchup_process()


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
            self.log.info('Ready signal received from a SB builder')
            self.sbb_state.set_sbb_ready()

        elif msg_type == MessageType.PENDING_TRANSACTIONS:
            self.sbb_state.set_pending_work(sbb_index)

        elif msg_type == MessageType.NO_TRANSACTIONS:
            self.sbb_state.set_no_work(sbb_index)

        elif msg_type == MessageType.SUBBLOCK_CONTENDER:
            await self._handle_sbc(sbb_index, msg, mtype_enc, msg_blob)

    async def handle_sub_msg(self, frames):
        self.log.success('GOT A SUB MESSAGE ON SBB MGR')
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
            self.set_masternode_ready(sender)

        # Process block notification messages
        elif msg_type == MessageType.BLOCK_NOTIFICATION:
            self.log.important3("Got BlockNotification from {} with hash {}"
                                .format(sender, msg.blockHash.hex()))

            # Process accordingly
            await self.sb_mgr.handle_block_notification(msg, sender)


    async def handle_router_msg(self, frames):
        sender, msg_type, msg_blob = frames

        msg_type, msg, signer, timestamp, is_verified = Message.unpack_message(msg_type, msg_blob)
        if not is_verified:
            self.log.error("Failed to verify the message of type {} from {} at {}. Ignoring it .."
                          .format(msg_type, signer, timestamp))
            return


    # todo
    # raw message -> action map and decoded message -> action maps?
    # actually add an internal function(s) to Message that can repack with or without signature ?
    async def _handle_sbc(self, sbb_index: int, sbc, mtype_enc: bytes, msg_blob: bytes):
        self.log.important("Got SBC with sb-index {} input-hash {}"
                           .format(sbc.subBlockIdx, sbc.inputHash.hex()))

        self.sb_mgr.sb_handler.add_sub_block(sbc)

        # first sign the message 
        mtype_sgn, msg_sgn = Message.get_message_signed_internal(
                                  signee=self.wallet.verifying_key(),
                                  sign=self.wallet.sign,
                                  msg_type=mtype_enc, msg=msg_blob)
        self.pub.send_msg(filter=DEFAULT_FILTER.encode(),
                          msg_type=mtype_sgn, msg=msg_sgn)

    # TODO make this DRY
    def _send_msg_over_ipc(self, sb_index: int, msg_type, message):
        """
        Convenience method to send a message over IPC router socket to a particular SBB process. Includes a
        frame to identify the type of message
        """
        self.log.spam("Sending msg to sb_index {} with payload {}".format(sb_index, message))

        id_frame = str(sb_index).encode()
        self.ipc_router.send_multipart([id_frame, msg_type, message])


    def send_ipc_message(self, msg_type: bytes, msg: bytes):
        for idx in range(self.sb_mapper.num_sb_builders):
            self.ipc_router.send_multipart([str(idx).encode(), msg_type, msg])

    async def wait_for_work(self):
        # return immediately if at least one sb has some work, otherwise wait
        wait_time = 0
        while not self.sbb_state.is_ready_for_next_sb() and \
              wait_time < BLOCK_HEART_BEAT_INTERVAL:
            await asyncio.sleep(1)
            wait_time += 1
        if wait_time > 0:
            blk_str = "block" if self.sbb_state.is_ready_for_next_sb() \
                      else "empty block"
            self.log.info("Waited for {} secs to make next {}"
                          .format(wait_time, blk_str))


    def send_make_next_sb(self):
        # first wait until there is some work or timeout
        asyncio.get_event_loop().run_until_complete(self.wait_for_work())

        msg_type, msg = Message.get_message_packed(MessageType.MAKE_NEXT_SB)
        self.send_ipc_message(msg_type, msg)

    def send_commit_cur_sb(self):
        msg_type, msg = Message.get_message_packed(MessageType.COMMIT_CUR_SB)
        self.send_ipc_message(msg_type, msg)

    def send_discord_cur_sb_and_align(self, sb_numbers, input_hashes):
        assert len(sb_numbers) == self.sb_mapper.num_sb_builders, "wrong num sb"
        assert len(input_hashes) == self.sb_mapper.num_sb_builders, "wrong num ih"
        for i in range(self.sb_mapper.num_sb_builders):
            mtype, msg = Message.get_message_packed(MessageType.DISCORD_AND_ALIGN,
                                                    subBlockNum=sb_numbers[i],
                                                    inputHashes=input_hashes[i])
            self.ipc_router.send_multipart([str(idx).encode(), mtype, msg])

