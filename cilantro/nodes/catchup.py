import asyncio, zmq.asyncio, zmq
from cilantro.logger import get_logger
from cilantro.constants.zmq_filters import *

from cilantro.messages.block_data.block_data import BlockData
from cilantro.messages.block_data.state_update import BlockIndexRequest, BlockIndexReply, BlockDataRequest
from cilantro.nodes.masternode.mn_api import StorageDriver
from cilantro.storage.state import StateDriver
from cilantro.nodes.masternode.master_store import MasterOps
from cilantro.storage.vkbook import VKBook
from cilantro.nodes.masternode.mn_api import StorageDriver
from cilantro.protocol.reactor.lsocket import LSocket

from collections import defaultdict
from typing import List, Union


BLOCK_REQUEST_TIMEOUT = 12  # How long we will wait for a BlockDataReply before we get upset


class CatchupManager:
    def __init__(self, verifying_key: str, pub_socket: LSocket, router_socket: LSocket, store_full_blocks=True):
        self.log = get_logger("CatchupManager")
        self.pub, self.router = pub_socket, router_socket
        self.verifying_key = verifying_key
        self.store_full_blocks = store_full_blocks
        self.all_masters = set(VKBook.get_masternodes()) - set(self.verifying_key)

        self.mns_replied_idx = set()  # a set of masternode vk's who have sent BlockIndexReplies

        self.curr_hash, self.curr_num = StateDriver.get_latest_block_info()
        self.target_blk_num = self.curr_num
        self.pending_block_updates = defaultdict(dict)  # this could be a priority queue of

    # Class internal
    async def _check_block_data_reply_recv(self, block_num):
        await asyncio.sleep(BLOCK_REQUEST_TIMEOUT)
        if block_num in self.pending_block_updates:
            # TODO re-request it or something, don't just blow up lol
            raise Exception("BlockDataReply for block number {} with data {} not receieved in {} seconds!"
                            .format(block_num, self.pending_block_updates[block_num], BLOCK_REQUEST_TIMEOUT))

    # BOTH WILL USE THIS
    def is_db_updated(self) -> bool:
        # TODO implement. return true when we are caught up
        return True

    # other
    def _add_pending_blocks(self, block_num: int, block_hash: str, mn_vks: List[list]):
        if self.curr_num >= block_num:
            self.log.spam("Block number {} is less than our current block number {}".format(block_num, self.curr_num))
            return

        if block_num in self.pending_block_updates:
            self.log.debugv("Block number {} already in pending_block_updates".format(block_num))
            return

        self.log.info("")

    def _has_enough_idx_replies(self):
        # We have enough BlockIndexReplies if 2/3 of Masternodes replied
        return len(self.mns_replied_idx) >= len(VKBook.get_masternodes()) * 2/3

    # Receiver Master only logic

    # ONLY MASTERNODES USE THIS
    def recv_block_idx_req(self, requester_vk: str, request: BlockIndexRequest):
        """
        Receive BlockIndexRequests calls storage driver to process req and build response
        :param requester_vk:
        :param request:
        :return:
        """
        assert self.store_full_blocks, "Must be able to store full blocks to reply to state update requests"
        delta_idx = StorageDriver.process_catch_up_idx(vk = requester_vk, curr_blk_hash = request.block_hash)
        self._send_block_idx_reply(catchup_list = delta_idx)

    def _send_block_idx_reply(self, catchup_list=None):
        # TODO do i need to build a list ?
        pass

    # ONLY MASTER NODES WILL USE THIS
    def recv_block_data_req(self, requester_vk: str, request: BlockDataRequest):
        req_blk = MasterOps.get_full_blk(blk_num = request.block_num)
        self._send_block_data_req(requester_vk, req_blk)
        pass

    def _send_block_data_reply(self):
        pass

    # Requester common MN DN logic

    # Phase I start
    def send_block_idx_req(self):
        """
        Multi-casting BlockIndexRequests to all master nodes with current block hash
        :return:
        """
        curr_hash = StateDriver.get_latest_block_hash()
        self.log.info("Multi cast BlockIndexRequests to all MN with current block hash {}".format(curr_hash))

        req = BlockIndexRequest.create(block_hash=curr_hash)
        self.pub.send_msg(req, header=CATCHUP_MN_DN_FILTER.encode())

    def recv_block_idx_reply(self, sender_vk: str, reply: BlockIndexReply):
        """
        We expect to receive this message from all master except requestor
        :param sender_vk:
        :param reply:
        :return:
        """
        self.mns_replied_idx.add(sender_vk)
        # plugin TODO process_received_idx
        if not reply.indices:
            self.log.info("Received BlockIndexReply with no new blocks from masternode {}".format(sender_vk))
            return

        for t in reply.indices:
            block_hash, block_num, mn_vks = t
            self._add_pending_blocks(block_num, block_hash, mn_vks)

    # Phase II start
    # private method
    def _send_block_data_req( self, mn_vk, req_blk_num):
        self.log.info("Unicast BlockDateRequests to masternode owner with current block num {} key {}"
                      .format(req_blk_num, mn_vk))
        req = BlockDataRequest.create(block_num = req_blk_num)
        self.router.send_msg(req, header=mn_vk.encode())

    # def request_block_data(self, mn_vk: str, block_hashes: Union[str, List[str]]):
    #     if type(block_hashes) is str:
    #         block_hashes = [block_hashes]
    #
    #     # request block hash via router socket with masternode vks
    #     msg = None  # TODO build foreal
    #     self.router.send_msg(msg, header=mn_vk.encode())

    # BOTH WILL RECV THIS (PHASE 2 REPLY)
    def recv_block_data_reply( self, reply: BlockData):
        if StorageDriver.process_received_block(block = reply):
            StateDriver.update_with_block(block = reply)
