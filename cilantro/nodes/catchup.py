import time
import asyncio
import math
from collections import defaultdict
from cilantro.logger import get_logger
from cilantro.constants.zmq_filters import *
from cilantro.protocol.comm.lsocket import LSocketBase
from cilantro.storage.vkbook import VKBook
from cilantro.storage.state import StateDriver
from cilantro.storage.redis import SafeRedis
from cilantro.storage.contracts import seed_contracts
from cilantro.nodes.masternode.mn_api import StorageDriver
from cilantro.nodes.masternode.master_store import MasterOps
from cilantro.messages.block_data.block_data import BlockData
from cilantro.messages.block_data.block_metadata import BlockMetaData
from cilantro.messages.block_data.state_update import BlockIndexRequest, BlockIndexReply, BlockDataRequest, BlockDataReply


IDX_REPLY_TIMEOUT = 20
TIMEOUT_CHECK_INTERVAL = 1


class CatchupManager:
    def __init__(self, verifying_key: str, pub_socket: LSocketBase, router_socket: LSocketBase, store_full_blocks=True):
        """

        :param verifying_key: host vk
        :param pub_socket:
        :param router_socket:
        :param store_full_blocks: Master node uses this flag to indicate block storage
        """
        self.log = get_logger("CatchupManager")

        # infra input
        self.pub, self.router = pub_socket, router_socket
        self.verifying_key = verifying_key
        self.store_full_blocks = store_full_blocks

        # catchup state
        self.is_caught_up = False
        self.timeout_catchup = time.time()      # 10 sec time we will wait for 2/3rd MN to respond
        self.node_idx_reply_set = set()  # num of master responded to catch up req

        # main list to process
        self.block_delta_list = []       # list of mn_index dict to process

        # received full block could be out of order
        self.rcv_block_dict = {}                 # DS stores any Out of order received blocks

        # loop to schedule timeouts
        self.timeout_fut = None

        # masternode should make sure redis and mongo are in sync
        if store_full_blocks:
            self.update_redis_state()

        self.curr_hash, self.curr_num = StateDriver.get_latest_block_info()
        self.target_blk_num = self.curr_num
        self.awaited_blknum = None

    def update_redis_state(self):
        """
        Sync block and state DB if either is out of sync.
        :return:
        """
        db_latest_blk_num = StorageDriver.get_latest_block_num()
        latest_state_num = StateDriver.get_latest_block_num()
        if db_latest_blk_num < latest_state_num:
            # TODO - assert and quit
            self.log.fatal("Block DB block - {} is behind StateDriver block - {}. Cannot handle"
                           .format(db_latest_blk_num, latest_state_num))
            # we need to rebuild state from scratch
            latest_state_num = 0
            SafeRedis.flushdb()
            seed_contracts()

        if db_latest_blk_num > latest_state_num:
            self.log.info("StateDriver block num {} is behind DB block num {}".format(latest_state_num, db_latest_blk_num))
            while latest_state_num < db_latest_blk_num:
                latest_state_num = latest_state_num + 1
                # TODO get nth full block wont work for now in distributed storage
                blk_dict = StorageDriver.get_nth_full_block(given_bnum=latest_state_num)
                if '_id' in blk_dict:
                    del blk_dict['_id']
                block = BlockData.from_dict(blk_dict)
                StateDriver.update_with_block(block = block)
        self.log.info("Verify StateDriver num {} StorageDriver num {}".format(latest_state_num, db_latest_blk_num))

    # should be called only once per node after bootup is done
    def run_catchup(self, ignore=False):
        self.log.important3("-----RUN-----")
        # check if catch up is already running
        if ignore and self.is_catchup_done():
            self.log.warning("Already caught up. Ignoring to run it again.")
            return

        # first reset state variables
        self.node_idx_reply_set.clear()
        self.is_caught_up = False
        # self.curr_hash, self.curr_num = StateDriver.get_latest_block_info()
        # self.target_blk_num = self.curr_num
        # self.awaited_blknum = None

        # starting phase I
        self.timeout_catchup = time.time()
        self.send_block_idx_req()

        self._reset_timeout_fut()
        # first time wait longer than usual
        time.sleep(3 * TIMEOUT_CHECK_INTERVAL)
        self.timeout_fut = asyncio.ensure_future(self._check_timeout())
        self.log.important2("Running catchup!")
        self.dump_debug_info(lnum = 111)

    def _reset_timeout_fut(self):
        if self.timeout_fut:
            if not self.timeout_fut.done():
                # TODO not sure i need this try/execpt here --davis
                try: self.timeout_fut.cancel()
                except: pass
            self.timeout_fut = None

    async def _check_timeout(self):
        async def _timeout():
            elapsed = 0
            self.log.important3("-----CHK-----")
            while elapsed < IDX_REPLY_TIMEOUT:
                elapsed += TIMEOUT_CHECK_INTERVAL
                await asyncio.sleep(TIMEOUT_CHECK_INTERVAL)

                if self._check_idx_reply_quorum() is True:
                    self.log.debugv("Quorum reached!")
                    return

            # If we have not returned from the loop and the this task has not been canceled, initiate a retry
            self.log.warning("Timeout of {} reached waiting for block idx replies! Resending BlockIndexRequest".format(IDX_REPLY_TIMEOUT))
            self.timeout_fut = None
            self.run_catchup(ignore=True)

        try:
            await _timeout()
        except asyncio.CancelledError as e:
            pass

    # Phase I start
    def send_block_idx_req(self):
        """
        Multi-casting BlockIndexRequests to all master nodes with current block hash
        :return:
        """
        self.log.info("Multi cast BlockIndexRequests to all MN with current block hash {}".format(self.curr_hash))
        # self.log.important3("Multi cast BlockIndexRequests to all MN with current block hash {}".format(self.curr_hash))  # TODO remove
        req = BlockIndexRequest.create(block_hash=self.curr_hash)
        self.pub.send_msg(req, header=CATCHUP_MN_DN_FILTER.encode())

        # self.log.important2("SEND BIR")
        self.dump_debug_info(lnum = 155)

    def _recv_block_idx_reply(self, sender_vk: str, reply: BlockIndexReply):
        """
        We expect to receive this message from all mn/dn
        :param sender_vk:
        :param reply:
        :return:
        """
        # self.log.important("Got blk index reply from sender {}\nreply: {}".format(sender_vk, reply))
        if sender_vk in self.node_idx_reply_set:
            return      # already processed

        if not reply.indices:
            self.node_idx_reply_set.add(sender_vk)
            self.log.important("Received BlockIndexReply with no index info from masternode {}".format(sender_vk))
            return

        tmp_list = reply.indices
        assert tmp_list[0].get('blockNum') <= tmp_list[-1].get('blockNum'), "ensure reply are in ascending order"
        # Todo @tejas we need to think if we need reverse sort here
        tmp_list.reverse()
        self.log.important2("tmp list -> {}".format(tmp_list))
        self.new_target_blk_num = tmp_list[-1].get('blockNum')
        new_blks = self.new_target_blk_num - self.target_blk_num

        if new_blks > 0:
            self.target_blk_num = self.new_target_blk_num
            update_list = tmp_list[-new_blks:]
            # self.log.important("update list {}".format(update_list))
            self.block_delta_list.extend(update_list)
            # self.dump_debug_info()
            if self.awaited_blknum == self.curr_num:
                self.awaited_blknum += 1
                self.process_recv_idx()

            if not self.awaited_blknum:
                self.awaited_blknum = self.curr_num
                self.process_recv_idx()

        self.node_idx_reply_set.add(sender_vk)
        self.log.debugv("new target block num {}\ntarget block num {}\ntemp list {}"
                        .format(self.new_target_blk_num, self.target_blk_num, tmp_list))
        self.dump_debug_info(lnum = 195)

    def recv_block_idx_reply(self, sender_vk: str, reply: BlockIndexReply):
        self._recv_block_idx_reply(sender_vk, reply)
        # self.log.important2("RCV BIRp")
        self.dump_debug_info(lnum = 200)
        return self.is_catchup_done()

    def _send_block_data_req(self, mn_vk, req_blk_num):
        self.log.info("Unicast BlockDateRequests to masternode owner with current block num {} key {}"
                      .format(req_blk_num, mn_vk))
        req = BlockDataRequest.create(block_num = req_blk_num)
        self.router.send_msg(req, header=mn_vk.encode())
        # self.log.important2("SEND BDRq")
        self.dump_debug_info(lnum = 209)

    def _recv_block_data_reply(self, reply: BlockData):
        # check if given block is older thn expected drop this reply
        # check if given blocknum grter thn current expected blk -> store temp
        # if given block needs to be stored update state/storage delete frm expected DT
        self.log.debugv("Got BlockData reply for block hash {}".format(reply.block_hash))
        self.dump_debug_info(lnum = 216)

        rcv_blk_num = reply.block_num
        if rcv_blk_num <= self.curr_num:
            self.log.debug("dropping already processed blk reply blk-{}:hash-{} ".format(reply.block_num, reply.block_hash))
            return

        self.rcv_block_dict[rcv_blk_num] = reply
        if rcv_blk_num > self.awaited_blknum:
            self.log.debug("Got block num {}, still awaiting block num {}".format(rcv_blk_num, self.awaited_blknum))
            return

        if (rcv_blk_num == self.awaited_blknum):
            self.curr_num = self.awaited_blknum
            self.update_received_block(block = reply)
            self.process_recv_idx()

    def recv_block_data_reply(self, reply: BlockData):
        # self.log.important("recv block data reply {}".format(reply))   # TODO remove
        self._recv_block_data_reply(reply)
        # self.log.important2("RCV BDRp")
        self.dump_debug_info(lnum = 231)
        return self.is_catchup_done()

    # MASTER ONLY CALL
    def recv_block_idx_req(self, requester_vk: str, request: BlockIndexRequest):
        """
        Receive BlockIndexRequests calls storage driver to process req and build response
        :param requester_vk:
        :param request:
        :return:
        """
        assert self.store_full_blocks, "Must be able to store full blocks to reply to state update requests"
        self.log.debugv("Got block index request from sender {} requesting block hash {} my_vk {}"
                        .format(requester_vk, request.block_hash, self.verifying_key))

        if requester_vk == self.verifying_key:
            self.log.debugv("received request from myself dropping the req")
            return

        if self.is_caught_up:
            self.curr_hash, self.curr_num = StateDriver.get_latest_block_info()

        delta_idx = self.get_idx_list(vk = requester_vk, latest_blk_num = self.curr_num,
                                      sender_bhash = request.block_hash)
        self.log.important2("Delta list {} for blk_num {} blk_hash {}".format(delta_idx, self.curr_num,
                                                                              request.block_hash))

        assert delta_idx[0].get('blockNum') <= delta_idx[-1].get('blockNum'), "ensure reply are in ascending order {}"\
            .format(delta_idx)

        # self.log.important2("RCV BIR")
        self.dump_debug_info(lnum = 258)
        self._send_block_idx_reply(reply_to_vk = requester_vk, catchup_list = delta_idx)

    def _recv_blk_notif(self, update: BlockMetaData):
        # can get any time - hopefully one incremental request, how do you handle it in all cases?
        nw_blk_num = update.block_num
        if self.is_caught_up:
            self.curr_hash, self.curr_num = StateDriver.get_latest_block_info()
            self.target_blk_num = self.curr_num
            self.awaited_blknum = None
        if (nw_blk_num <= self.curr_num) or (nw_blk_num <= self.target_blk_num):
            return
        if nw_blk_num > (self.target_blk_num + 1):
            self.run_catchup()
        else:
            # actually you can request block data directly
            # elem = {}
            # elem["blockNum"] = nw_blk_num
            # elem["blockHash"] = update.block_hash
            # elem["blockOwners"] = update.block_owners
            # self.block_delta_list.append(elem)
            self.is_caught_up = False
            self.target_blk_num = nw_blk_num
            for vk in update.block_owners:
                self._send_block_data_req(mn_vk = vk, req_blk_num = nw_blk_num)

    def recv_new_blk_notif(self, update: BlockMetaData):
        self._recv_blk_notif(update)
        return self.is_catchup_done()

    # todo handle mismatch between redis and monodb
    # MASTER ONLY CALL
    def _send_block_idx_reply(self, reply_to_vk = None, catchup_list=None):
        # this func doesnt care abt catchup_state we respond irrespective
        self.log.important2("catchup list -> {}".format(catchup_list))
        reply = BlockIndexReply.create(block_info = catchup_list)
        self.log.debugv("Sending block index reply to vk {}, catchup {}".format(reply_to_vk, catchup_list))
        self.router.send_msg(reply, header=reply_to_vk.encode())
        # self.log.important2("SEND BIRp")
        self.dump_debug_info(lnum = 296)

    # MASTER ONLY CALL
    def recv_block_data_req(self, sender_vk: str, req: BlockDataRequest):
        blk_dict = StorageDriver.get_nth_full_block(given_bnum=req.block_num)
        if '_id' in blk_dict:
            del blk_dict['_id']
        block = BlockData.from_dict(blk_dict)
        reply = BlockDataReply.create_from_block(block)
        self.router.send_msg(reply, header=sender_vk.encode())

    def get_idx_list(self, vk, latest_blk_num, sender_bhash):
        # check if requester is master or del
        valid_node = VKBook.is_node_type('masternode', vk) or VKBook.is_node_type('delegate', vk)
        if valid_node is True:
            given_blk_num = MasterOps.get_blk_num_frm_blk_hash(blk_hash = sender_bhash)

            self.log.debugv('given block is already latest hash - {} givenblk - {} curr-{}'
                           .format(sender_bhash, given_blk_num, latest_blk_num))

            if given_blk_num == latest_blk_num:
                self.log.debug('given block is already latest')
                return None
            else:
                idx_delta = MasterOps.get_blk_idx(n_blks = (latest_blk_num - given_blk_num))
                return idx_delta

        assert valid_node is True, "invalid vk given key is not of master or delegate dumping vk {}".format(vk)
        pass

    # removed flooding, but it could be too sequential?
    # use futures to control rate of requests?
    def process_recv_idx(self):
        if (self.awaited_blknum <= self.curr_num) and (self.awaited_blknum < self.target_blk_num):
            self.awaited_blknum = self.curr_num + 1
            self.dump_debug_info(lnum = 337)
            # don't request if it is in stashed list. move to next one
            while self.awaited_blknum in self.rcv_block_dict:
                self.awaited_blknum = self.awaited_blknum + 1
            blknum = 0
            blk_ptr = None
            while (blknum < self.awaited_blknum) and len(self.block_delta_list):
                blk_ptr = self.block_delta_list.pop(0)
                blknum = blk_ptr.get('blockNum')
            assert blk_ptr and (blknum == self.awaited_blknum), "can't find the index infor for the block num {}".format(self.awaited_blknum)
            mn_list = blk_ptr.get('blockOwners')
            for vk in mn_list:
                self._send_block_data_req(mn_vk = vk, req_blk_num = self.awaited_blknum)

    def update_received_block(self, block = None):
        assert self.curr_num in self.rcv_block_dict, "not found the received block!"
        cur_num = self.curr_num
        while cur_num in self.rcv_block_dict:
            block = self.rcv_block_dict[cur_num]
            if self.store_full_blocks is True:
                update_blk_result = bool(MasterOps.evaluate_wr(entry = block._data.to_dict()))
                assert update_blk_result is True, "failed to update block"

            StateDriver.update_with_block(block = block)
            self.curr_num = cur_num
            cur_num = cur_num + 1
        self.curr_hash, self.curr_num = StateDriver.get_latest_block_info()

    def _check_idx_reply_quorum(self):
        # We have enough BlockIndexReplies if 2/3 of Masternodes replied
        min_quorum = math.ceil(len(VKBook.get_masternodes()) * 2/3)
        if self.store_full_blocks:
            min_quorum -= 1   # -1 so we dont include ourselves if we are a MN
        return len(self.node_idx_reply_set) >= min_quorum

    def is_catchup_done(self):
        if self.is_caught_up:
            return True
        self.is_caught_up = (self.target_blk_num == self.curr_num) and \
                            self._check_idx_reply_quorum()

        # DEBUG
        # self.log.debugv("target blk num {}".format(self.target_blk_num))
        # self.log.debugv("awaited blk num {}".format(self.awaited_blknum))
        # self.log.debugv("curr_num {}".format(self.curr_num))
        # self.log.debugv("self._check_idx_reply_quorum() {}".format(self._check_idx_reply_quorum()))
        # self.log.debugv("self.is_caught_up {}".format(self.is_caught_up))
        # END DEBUG
        # if self.is_caught_up:       # reset here
            # self.node_idx_reply_set.clear()
        self.dump_debug_info(lnum = 380)

        return self.is_caught_up

    def dump_debug_info(self, lnum = None):
        # TODO change this log to important for debugging

        self.log.debugv("lnum -> {}".format(lnum))
        self.log.debugv("Time -> {}".format(self.timeout_catchup))
        self.log.debugv("is_caught_up -> {}".format(self.is_caught_up))
        self.log.debugv("target blk num -> {}".format(self.target_blk_num))
        self.log.debugv("awaited blk num -> {}".format(self.awaited_blknum))
        self.log.debugv("curr_num -> {}".format(self.curr_num))
        self.log.debugv("curr_hash -> {}".format(self.curr_hash))

        self.log.debugv("Pending blk list -> {}".format(self.block_delta_list))
        self.log.debugv("Received blk dict -> {}".format(self.rcv_block_dict))

        self.log.debugv("quorum nodes -> {}".format(self.node_idx_reply_set))
        self.log.debugv("self._check_idx_reply_quorum() -> {}".format(self._check_idx_reply_quorum()))

