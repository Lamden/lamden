import timeit
from collections import defaultdict
from cilantro.logger import get_logger
from cilantro.constants.zmq_filters import *
from cilantro.protocol.reactor.lsocket import LSocket
from cilantro.storage.vkbook import VKBook
from cilantro.storage.state import StateDriver
from cilantro.nodes.masternode.mn_api import StorageDriver
from cilantro.storage.mongo import MDB
from cilantro.nodes.masternode.master_store import MasterOps
from cilantro.messages.block_data.block_data import BlockData, BlockMetaData
from cilantro.messages.block_data.state_update import BlockIndexRequest, BlockIndexReply, BlockDataRequest


class CatchupManager:
    def __init__(self, verifying_key: str, pub_socket: LSocket, router_socket: LSocket):
        self.log = get_logger("CatchupManager")

        # infra input
        self.pub, self.router = pub_socket, router_socket
        self.verifying_key = verifying_key
        self.store_full_blocks = None

        # catchup state
        self.catchup_state = False


        # main list to process
        self.block_delta_list = []      # list of mn_index dict to process
        self.target_blk = {}            # last block in list
        self.target_blk_num = None

        # process send
        self.blk_req_ptr = {}           # current ptr track send blk req
        self.blk_req_ptr_idx = None     # idx to track ptr in block_delta_list
        self.last_req_blk_num = None

        self.curr_hash, self.curr_num = None, None      # latest blk on redis

        # received full block could be out of order
        self.rcv_block_dict = {}
        self.awaited_blknum = None      # catch up waiting on this blk num

        self.run_catchup()

    def run_catchup(self, store_full_blocks=True):
        # check if catch up is already running
        if self.catchup_state is True:
            self.log.critical("catch up already running we shouldn't be here")
            return

        self.store_full_blocks = store_full_blocks
        #self.all_masters = set(VKBook.get_masternodes())
        self.curr_hash, self.curr_num = StateDriver.get_latest_block_info()

        # starting phase I
        self.catchup_state = self.send_block_idx_req()

    # Phase I start
    def send_block_idx_req(self):
        """
        Multi-casting BlockIndexRequests to all master nodes with current block hash
        :return:
        """
        self.log.info("Multi cast BlockIndexRequests to all MN with current block hash {}".format(self.curr_hash))
        req = BlockIndexRequest.create(block_hash=self.curr_hash)
        self.pub.send_msg(req, header=CATCHUP_MN_DN_FILTER.encode())
        return True

    def recv_block_idx_reply(self, sender_vk: str, reply: BlockIndexReply):
        """
        We expect to receive this message from all mn/dn
        :param sender_vk:
        :param reply:
        :return:
        """

        if not reply.indices:
            self.log.info("Received BlockIndexReply with no new blocks from masternode {}".format(sender_vk))
            return

        if not self.block_delta_list:                              # for boot phase
            self.block_delta_list = reply.indices
            self.target_blk = self.block_delta_list[len(self.block_delta_list) - 1]
            self.target_blk_num = self.target_blk.get('blockNum')
            self.blk_req_ptr_idx = 0
            self.blk_req_ptr = self.block_delta_list[self.blk_req_ptr_idx]           # 1st blk req to send
            self.last_req_blk_num = self.blk_req_ptr.get('blockNum')
        else:                                              # for new request
            tmp_list = reply.indices
            new_target_blk = tmp_list[len(tmp_list)-1]
            new_blks = new_target_blk.get('blockNum') - self.target_blk.get('blockNum')
            if new_blks > 0:
                # find range to be split from new list
                upper_idx = len(tmp_list) - 1
                lower_idx = upper_idx - new_blks
                verify_blk = tmp_list[lower_idx]
                assert verify_blk.get('blockNum') == new_target_blk.get('blockNum'), "something is wrong split is not" \
                                                                                     " getting us to current blk"
                # slicing new list and appending list
                update_list = tmp_list[lower_idx:len(tmp_list)]
                self.block_delta_list.append(update_list)
                self.target_blk = self.block_delta_list[len(self.block_delta_list) - 1]
                self.target_blk_num = self.target_blk.get('blockNum')

        self.process_recv_idx()

    def _send_block_data_req(self, mn_vk, req_blk_num):
        self.log.info("Unicast BlockDateRequests to masternode owner with current block num {} key {}"
                      .format(req_blk_num, mn_vk))
        req = BlockDataRequest.create(block_num = req_blk_num)
        self.router.send_msg(req, header=mn_vk.encode())
        if self.awaited_blknum is None:
            self.awaited_blknum = req_blk_num

    def recv_block_data_reply(self, reply: BlockData):
        # check if given block is older thn expected drop this reply
        # check if given blocknum grter thn current expected blk -> store temp
        # if given block needs to be stored update state/storage delete frm expected DT

        block_dict = MDB.get_dict(reply)
        self.awaited_blknum = self.block_delta_list[0]
        rcv_blk_num = block_dict.get('blockNum')

        if rcv_blk_num <= self.curr_num:
            self.log.debug("dropping giving blk reply blk-{}:hash-{} ".format(reply.block_num, reply.block_hash))
            return

        if rcv_blk_num > self.awaited_blknum:
            self.rcv_block_dict[rcv_blk_num] = reply

        if rcv_blk_num == self.awaited_blknum:
            if self.update_received_block(block = block_dict) and self.store_full_blocks is True:
                StateDriver.update_with_block(block = reply)
            else:
                StateDriver.update_with_block(block = reply)

            self.update_catchup_state(block_num = rcv_blk_num)

    # MASTER ONLY CALL
    def recv_block_idx_req(self, requester_vk: str, request: BlockIndexRequest):
        """
        Receive BlockIndexRequests calls storage driver to process req and build response
        :param requester_vk:
        :param request:
        :return:
        """
        assert self.store_full_blocks, "Must be able to store full blocks to reply to state update requests"
        delta_idx = self.get_delta_idx(vk = requester_vk, curr_blk_num = self.curr_num,
                                       sender_blk_hash = request.block_hash)
        self._send_block_idx_reply(catchup_list = delta_idx)

    # MASTER ONLY CALL
    def _send_block_idx_reply(self, reply_to_vk = None, catchup_list=None):
        # this func doesnt care abt catchup_state we respond irrespective
        reply = BlockIndexReply.create(block_info = catchup_list)
        self.router.send_msg(reply, header=reply_to_vk.encode())

    @classmethod
    def get_delta_idx(cls, vk = None, curr_blk_num = None, sender_blk_hash = None):
        """
        API gets latest hash requester has and responds with delta block index

        :param vk: mn or dl verifying key
        :param curr_blk_hash:
        :return:
        """
        # check if requester is master or del
        valid_node = bool(VKBook.get_masternodes().index(vk)) or bool(VKBook.get_delegates().index(vk))
        if valid_node is True:
            given_blk_num = MasterOps.get_blk_num_frm_blk_hash(blk_hash = sender_blk_hash)
            latest_blk_num = curr_blk_num

            if given_blk_num == latest_blk_num:
                cls.log.debug('given block is already latest')
                return None
            else:
                idx_delta = MasterOps.get_blk_idx(n_blks = (latest_blk_num - given_blk_num))
                return idx_delta

        assert valid_node is True, "invalid vk given key is not of master or delegate dumping vk {}".format(vk)

    def process_recv_idx(self):
        assert self.last_req_blk_num <= self.target_blk_num, "our last request should never overshoot target blk"
        while self.last_req_blk_num <= self.target_blk_num:
            mn_list = self.blk_req_ptr.get('blk_req_ptr')
            for vk in mn_list:
                self._send_block_data_req(mn_vk = vk, req_blk_num = self.last_req_blk_num)

            self.blk_req_ptr_idx = self.blk_req_ptr_idx + 1
            self.blk_req_ptr = self.block_delta_list[self.blk_req_ptr_idx]
            self.last_req_blk_num = self.last_req_blk_num + 1

    @staticmethod
    def update_received_block(block = None):
        update_blk_result = bool(MasterOps.evaluate_wr(entry = block))
        assert update_blk_result is True, "failed to update block"
        return update_blk_result

    def update_catchup_state(self, block_num=None):
        """
        Called when we successfully update state and storage

        - cleans up stale states
        - updates expected/awaited block requirements
        - resets state if you are at end of catchup
        :param block_num:
        :return:
        """
        if block_num in self.rcv_block_dict.keys():
            self.rcv_block_dict.pop(block_num)





