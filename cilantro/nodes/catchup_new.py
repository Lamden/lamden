import timeit
from collections import defaultdict
from cilantro.logger import get_logger
from cilantro.constants.zmq_filters import *
from cilantro.protocol.reactor.lsocket import LSocket
from cilantro.storage.vkbook import VKBook
from cilantro.storage.state import StateDriver
from cilantro.nodes.masternode.mn_api import StorageDriver
from cilantro.nodes.masternode.master_store import MasterOps
from cilantro.messages.block_data.block_data import BlockData, BlockMetaData
from cilantro.messages.block_data.state_update import BlockIndexRequest, BlockIndexReply, BlockDataRequest


class CatchupUtil:
    @classmethod
    def get_delta_idx(cls, vk = None, curr_blk_num =None, sender_blk_hash = None):
        """
        API gets latest hash requester has and responds with delta block index

        :param vk: mn or dl verifying key
        :param curr_blk_hash:
        :return:
        """
        get_latest_block_hash
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

        assert valid_node is True, "invalid vk given key is not of master or delegate dumpting vk {}".format(vk)

    @classmethod
    def process_received_idx(cls, blk_idx_dict = None):
        """
        API goes list dict and sends out blk req for each blk num
        :param blk_idx_dict:
        :return:
        """
        last_elm_curr_list = sorted(cls.block_index_delta.keys())[-1]
        last_elm_new_list = sorted(blk_idx_dict.keys())[-1]

        if last_elm_curr_list > last_elm_new_list:
            cls.log.critical("incoming block delta is stale ignore continue wrk on old")
            return

        if last_elm_curr_list == last_elm_new_list:
            cls.log.info("delta is same returning")
            return

        if last_elm_curr_list < last_elm_new_list:
            cls.log.critical("we have stale list update working list ")
            cls.block_index_delta = blk_idx_dict
            last_elm_curr_list = last_elm_new_list

        while cls.send_req_blk_num < last_elm_curr_list:
            # look for active master in vk list
            avail_copies = len(cls.block_index_delta[cls.send_req_blk_num])
            if avail_copies < REPLICATION:
                cls.log.critical("block is under protected needs to re protect")

            while avail_copies > 0:
                vk = cls.block_index_delta[cls.send_req_blk_num][avail_copies - 1]
                if vk in VKBook.get_masternodes():
                    CatchupManager._send_block_data_req(mn_vk = vk, req_blk_num = cls.send_req_blk_num)
                    break
                avail_copies = avail_copies - 1  # decrement count check for another master

            cls.send_req_blk_num += 1
            # TODO we should somehow check time out for these requests


    @classmethod
    def process_received_block( cls, block = None ):
        block_dict = MDB.get_dict(block)
        update_blk_result = bool(MasterOps.evaluate_wr(entry = block_dict))
        assert update_blk_result is True, "failed to update block"
        return update_blk_result


class CatchupManager:
    def __init__(self, verifying_key: str, pub_socket: LSocket, router_socket: LSocket):
        self.log = get_logger("CatchupManager")

        self.pub, self.router = pub_socket, router_socket
        self.verifying_key = verifying_key

        self.catchup_state = False
        self.store_full_blocks = None
        self.target_blk = {}
        self.curr_hash, self.curr_num = None, None      # latest blk on redis
        self.blk_list = []
        self.all_masters = None

        # self.all_masters = set(VKBook.get_masternodes()) - set(self.verifying_key)
        # for block zero its going to just return 0x64 hash n 0 blk_num
        # self.pending_block_updates = defaultdict(dict)

        self.run_catchup()

    def run_catchup(self, store_full_blocks=True):
        # check if catch up is already running
        if self.catchup_state is True:
            self.log.critical("catch up already running we shouldn't be here")
            return

        self.store_full_blocks = store_full_blocks
        self.all_masters = set(VKBook.get_masternodes())
        self.curr_hash, self.curr_num = StateDriver.get_latest_block_info()

        # starting phase I
        self.catchup_state = self.send_block_idx_req()

    # Phase I start
    def send_block_idx_req(self):
        """
        Multi-casting BlockIndexRequests to all master nodes with current block hash
        :return:
        """
        self.log.info("Multi cast BlockIndexRequests to all MN with current block hash {}".format(curr_hash))
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

        if not self.blk_list:
            self.blk_list = reply.indices
            self.target_blk = self.blk_list[len(self.blk_list)-1]
        else:
            count = 0                                                               # num of new blk to update
            tmp_list = reply.indices
            new_target_blk = tmp_list[len(tmp_list)-1]
            while self.target_blk.get('blockNum') < new_target_blk.get('blockNum'):
                count = count +1
                # TODO
                pass

    def recv_block_data_reply( self, reply: BlockData):
        if StorageDriver.process_received_block(block = reply):
            StateDriver.update_with_block(block = reply)

    # MASTER ONLY CALLS
    def recv_block_idx_req(self, requester_vk: str, request: BlockIndexRequest):
        """
        Receive BlockIndexRequests calls storage driver to process req and build response
        :param requester_vk:
        :param request:
        :return:
        """
        assert self.store_full_blocks, "Must be able to store full blocks to reply to state update requests"
        delta_idx = CatchupUtil.get_delta_idx(vk = requester_vk, curr_blk_num = self.curr_num,
                                              sender_blk_hash = request.block_hash)
        self._send_block_idx_reply(catchup_list = delta_idx)

    def _send_block_idx_reply(self, reply_to_vk = None, catchup_list=None):
        # this func doesnt care abt catchup_state we respond irrespective
        reply = BlockIndexReply.create(block_info = catchup_list)
        self.router.send_msg(reply, header=reply_to_vk.encode())

    def _send_block_data_req(self, mn_vk, req_blk_num):
        self.log.info("Unicast BlockDateRequests to masternode owner with current block num {} key {}"
                      .format(req_blk_num, mn_vk))
        req = BlockDataRequest.create(block_num = req_blk_num)
        self.router.send_msg(req, header=mn_vk.encode())

