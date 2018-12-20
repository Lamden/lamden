import time, asyncio, math
from collections import defaultdict
from cilantro.logger import get_logger
from cilantro.constants.zmq_filters import *
from cilantro.protocol.reactor.lsocket import LSocket
from cilantro.storage.vkbook import VKBook
from cilantro.storage.state import StateDriver
from cilantro.nodes.masternode.mn_api import StorageDriver
from cilantro.storage.mongo import MDB
from cilantro.nodes.masternode.master_store import MasterOps
from cilantro.messages.block_data.block_data import BlockData
from cilantro.messages.block_data.block_metadata import NewBlockNotification
from cilantro.messages.block_data.state_update import BlockIndexRequest, BlockIndexReply, BlockDataRequest


IDX_REPLY_TIMEOUT = 10
TIMEOUT_CHECK_INTERVAL = 1

# start the catch manager when boot is done
# when we start catchup when listen is ready, we start the timer - sleep 1 sec
# broadcast the request. Don't reply to any other requests within 2 secs. use other broadcasts as replies
# after 2 secs, if we have at least one other request, we can start requesting other masters directly

class CatchupManager:
    def __init__(self, verifying_key: str, pub_socket: LSocket, router_socket: LSocket, store_full_blocks=True):
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
        self.catchup_state = False
        self.timeout_catchup = 0         # 10 sec time we will wait for 2/3rd MN to respond
        self.node_idx_reply_set = set()  # num of master responded to catch up req

        self.curr_hash, self.curr_num = StateDriver.get_latest_block_info()

        # main list to process
        self.block_delta_list = []       # list of mn_index dict to process
        self.target_blk_num = self.curr_num

        # received full block could be out of order
        self.rcv_block_dict = {}                 # DS stores any Out of order received blocks
        self.awaited_blknum = self.curr_num      # catch up waiting on this blk num

        # loop to schedule timeouts
        self.timeout_fut = None

    # should be called only once per node after bootup is done
    def run_catchup(self, ignore=False):
        # check if catch up is already running
        if not ignore and self.catchup_state is True:
            self.log.critical("catch up already running we shouldn't be here")
            return

        # starting phase I
        self.timeout_catchup = time.time()
        self.catchup_state = self.send_block_idx_req()

        self._reset_timeout_fut()
        # first time wait longer than usual
        time.sleep(3 * TIMEOUT_CHECK_INTERVAL)
        self.timeout_fut = asyncio.ensure_future(self._check_timeout())
        self.log.important2("run catchup")
        self.dump_debug_info()

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
        self.dump_debug_info()
        return True

    # raghu todo - recv functions can return the status of catchup - should be ignored by delegates
    def recv_block_idx_reply(self, sender_vk: str, reply: BlockIndexReply):
        """
        We expect to receive this message from all mn/dn
        :param sender_vk:
        :param reply:
        :return:
        """
        # self.log.important("Got blk index reply from sender {}\nreply: {}".format(sender_vk, reply))

        if sender_vk in self.node_idx_reply_set:
            return      # already processed

        self.node_idx_reply_set.add(sender_vk)

        if not reply.indices:
            self.log.important("Received BlockIndexReply with no index info from masternode {}".format(sender_vk))
            # self.log.important("responded mn - {}".format(self.node_idx_reply_set))
            # self.catchup_state = not self.check_catchup_done()
            self.check_catchup_done()
            self.dump_debug_info()
            return

        tmp_list = reply.indices
        self.new_target_blk_num = tmp_list[-1].get('blockNum')
        new_blks = self.new_target_blk_num - self.target_blk_num
        self.log.important("raghu nt {} tb {} tlist {}".format(self.new_target_blk_num, self.target_blk_num, tmp_list))
        if new_blks > 0:
            self.target_blk_num = self.new_target_blk_num
            update_list = tmp_list[-new_blks:]
            self.log.important("update list {}".format(update_list))
            self.block_delta_list.extend(update_list)
            # self.dump_debug_info()
            if not self.awaited_blknum:
                self.awaited_blknum = self.curr_num
                self.process_recv_idx()
        
        # self.log.important2("RCV BIRp")
        self.dump_debug_info()

    def _send_block_data_req(self, mn_vk, req_blk_num):
        self.log.info("Unicast BlockDateRequests to masternode owner with current block num {} key {}"
                      .format(req_blk_num, mn_vk))
        req = BlockDataRequest.create(block_num = req_blk_num)
        self.router.send_msg(req, header=mn_vk.encode())
        # if self.awaited_blknum is None:
            # self.awaited_blknum = req_blk_num
        # self.log.important2("SEND BDRq")
        self.dump_debug_info()

    def recv_block_data_reply(self, reply: BlockData):
        # check if given block is older thn expected drop this reply
        # check if given blocknum grter thn current expected blk -> store temp
        # if given block needs to be stored update state/storage delete frm expected DT
        self.log.debugv("Got BlockData reply for block hash {}".format(reply.block_hash))

        rcv_blk_num = reply.block_num
        if rcv_blk_num <= self.curr_num:
            self.log.debug("dropping already processed blk reply blk-{}:hash-{} ".format(reply.block_num, reply.block_hash))
            return

        self.rcv_block_dict[rcv_blk_num] = reply
        if rcv_blk_num > self.awaited_blknum:
            self.log.debug("This should not happen right now!")
            return

        # if (rcv_blk_num == self.awaited_blknum) and (self.awaited_blknum > self.curr_num):
        if (rcv_blk_num == self.awaited_blknum):
            self.curr_num = self.awaited_blknum
            self.process_recv_idx()
            self.update_received_block(block = reply)

        # self.log.important2("RCV BDRp")
        self.dump_debug_info()

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

        # need to reupdate self.curr_num if out of catch up mode  raghu todo
        delta_idx = self.get_idx_list(vk = requester_vk, latest_blk_num = self.curr_num,
                                      sender_bhash = request.block_hash)
        self.log.debugv("Delta list {}".format(delta_idx))

        # self.log.important2("RCV BIR")
        self.dump_debug_info()
        self._send_block_idx_reply(reply_to_vk = requester_vk, catchup_list = delta_idx)

    def recv_new_blk_notif(self, update: NewBlockNotification):
        # can get any time - hopefully one incremental request, how do you handle it in all cases?
        # if self.catchup_state is False:
            # self.log.error("Err we shouldn't be getting new with catchup False")
            # return

        nw_blk_num = update.block_num
        if self.catchup_state:
            self.curr_hash, self.curr_num = StateDriver.get_latest_block_info()
            self.target_blk_num = self.curr_num
            self.awaited_blknum = self.curr_num
        if (nw_blk_num <= self.curr_num) or (nw_blk_num <= self.target_blk_num):
            return
        if nw_blk_num > (self.target_blk_num + 1):
            self.catchup_state = False
            # todo reset needed ? rpc need to reset index reply set
            self.run_catchup(ignore=True)
        else: 
            self.target_blk_num = nw_blk_num
            if nw_blk_num > (self.curr_num + 1):
                self.awaited_blknum = nw_blk_num
                nw_blk_owners = update.block_owners
                for vk in nw_blk_owners:
                    self._send_block_data_req(mn_vk = vk, req_blk_num = nw_blk_num)
            else:
                # add it to the list 
                elem = {}
                elem["blockNum"] = nw_blk_num
                elem["blockHash"] = update.block_hash
                elem["blockOwners"] = update.block_owners
    

    # raghu todo check if indices are sent including the requested or not?
    # todo handle mismatch between redis and monodb
    # MASTER ONLY CALL
    def _send_block_idx_reply(self, reply_to_vk = None, catchup_list=None):
        # this func doesnt care abt catchup_state we respond irrespective
        reply = BlockIndexReply.create(block_info = catchup_list)
        self.log.debugv("Sending block index reply to vk {}, catchup {}".format(reply_to_vk, catchup_list))
        self.router.send_msg(reply, header=reply_to_vk.encode())
        # self.log.important2("SEND BIRp")
        self.dump_debug_info()

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
    # add 
    def process_recv_idx(self):
        if (self.awaited_blknum == self.curr_num) and (self.awaited_blknum < self.target_blk_num):
            self.awaited_blknum = self.awaited_blknum + 1
            # don't request if it is in stashed list. move to next one
            while self.awaited_blknum in self.rcv_block_dict:
                self.awaited_blknum = self.awaited_blknum + 1
            blknum = 0
            blk_ptr = None
            while (blknum < self.awaited_blknum) and len(self.block_delta_list):
                blk_ptr = self.block_delta_list.pop(0)
                self.log.important("{}".format(blk_ptr))
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

    # raghu todo do we reset when resend requests?
    def _check_idx_reply_quorum(self):
        # We have enough BlockIndexReplies if 2/3 of Masternodes replied
        min_quorum = math.ceil(len(VKBook.get_masternodes()) * 2/3) - 1   # -1 so we dont include ourselves
        return len(self.node_idx_reply_set) >= min_quorum

    def check_catchup_done(self):
        if self.catchup_state:
            return True
        # raghu reset stuff here?  todo
        self.catchup_state = self._check_idx_reply_quorum() and \
                             not self.block_delta_list
        return self.catchup_state

    def dump_debug_info(self):
        # TODO change this log to important for debugging
        self.log.spam("catchup Status => {}"
                            "---- data structures state----"
                            "Pending blk list -> {} "
                            "----Target-----"
                            "target_blk_num -> {}"
                            "----Current----"
                            "elf.curr_hash - {}, curr_num-{}"
                            "----send req----"
                            "----rcv req-----"
                            "rcv_block_dict - {}"
                            "awaited_blknum - {}"
                            .format(self.catchup_state, self.block_delta_list, self.target_blk_num,
                                    self.curr_hash, self.curr_num, 
                                    self.rcv_block_dict, self.awaited_blknum))
