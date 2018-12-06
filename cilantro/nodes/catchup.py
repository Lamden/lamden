import asyncio, zmq.asyncio, zmq
from cilantro.logger import get_logger
from cilantro.constants.zmq_filters import *

from cilantro.messages.block_data.block_data import BlockData, BlockMetaData
from cilantro.messages.block_data.state_update import BlockIndexRequest, BlockIndexReply

from cilantro.storage.state import StateDriver
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

        self.mns_replied_index = set()  # a set of masternode vk's who have sent BlockIndexReplies

        self.curr_hash, self.curr_num = StateDriver.get_latest_block_info()
        self.pending_block_updates = defaultdict(dict)  # this could be a priority queue of

    async def _check_block_reply_received(self, block_num):
        await asyncio.sleep(BLOCK_REQUEST_TIMEOUT)
        if block_num in self.pending_block_updates:
            # TODO re-request it or something, don't just blow up lol
            raise Exception("BlockDataReply for block number {} with data {} not receieved in {} seconds!"
                            .format(block_num, self.pending_block_updates[block_num], BLOCK_REQUEST_TIMEOUT))

    def recv_block_index_req(self, requester_vk: str, request: BlockIndexRequest):
        assert self.store_full_blocks, "Must be able to store full blocks to reply to state update requests"

        # TODO
        # get list of of lists of (blocks, blocks num, masternode_vks), and build BlockIndexReply
        # reply on router socket to requester vks via router socket

    def send_block_index_req(self):
        curr_hash = StateDriver.get_latest_block_hash()
        self.log.info("Multicasting BlockIndexRequests to all masternodes with current block hash {}".format(curr_hash))

        req = BlockIndexRequest.create(block_hash=curr_hash)
        self.pub.send_msg(req, header=MASTER_MASTER_FILTER.encode())

    def recv_index_reply(self, sender_vk: str, reply: BlockIndexReply):
        self.mns_replied_index.add(sender_vk)

        if not reply.indices:
            self.log.info("Received BlockIndexReply with no new blocks from masternode {}".format(sender_vk))
            return

        for t in reply.indices:
            block_hash, block_num, mn_vks = t
            self._add_pending_blocks(block_num, block_hash, mn_vks)

    def _add_pending_blocks(self, block_num: int, block_hash: str, mn_vks: List[list]):
        if self.curr_num >= block_num:
            self.log.spam("Block number {} is less than our current block number {}".format(block_num, self.curr_num))
            return

        if block_num in self.pending_block_updates:
            self.log.debugv("Block number {} already in pending_block_updates".format(block_num))
            return

        self.log.info("")

    def request_block_data(self, mn_vk: str, block_hashes: Union[str, List[str]]):
        if type(block_hashes) is str:
            block_hashes = [block_hashes]

        # request block hash via router socket with masternode vks
        msg = None  # TODO build foreal
        self.router.send_msg(msg, header=mn_vk.encode())

    def _has_enough_index_replies(self):
        # We have enough BlockIndexReplies if 2/3 of Masternodes replied
        return len(self.mns_replied_index) >= len(VKBook.get_masternodes()) * 2/3

