from cilantro.logger.base import get_logger
from cilantro.protocol.multiprocessing.worker import Worker
from cilantro.protocol.structures.merkle_tree import MerkleTree

from cilantro.storage.state import StateDriver
from cilantro.storage.vkbook import VKBook
from cilantro.nodes.catchup import CatchupManager
from cilantro.nodes.masternode.mn_api import StorageDriver
from cilantro.nodes.masternode.block_contender import BlockContender

from cilantro.constants.zmq_filters import *
from cilantro.constants.ports import MASTER_ROUTER_PORT, MASTER_PUB_PORT, DELEGATE_PUB_PORT, DELEGATE_ROUTER_PORT
from cilantro.constants.system_config import *

from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.consensus.sub_block_contender import SubBlockContender
from cilantro.messages.consensus.merkle_signature import MerkleSignature
from cilantro.messages.block_data.block_data import BlockData
from cilantro.messages.block_data.sub_block import SubBlock
from cilantro.messages.block_data.state_update import *
from cilantro.messages.block_data.block_metadata import NewBlockNotification
from cilantro.messages.transaction.data import TransactionData

from cilantro.utils.hasher import Hasher
from cilantro.protocol import wallet
from typing import List

import asyncio, zmq, os, time, itertools
from collections import defaultdict


class BlockAggregator(Worker):

    def __init__(self, ip, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = get_logger("BlockAggregator[{}]".format(self.verifying_key[:8]))
        self.ip = ip
        self.tasks = []

        self.curr_block_hash = StateDriver.get_latest_block_hash()
        self.curr_block = BlockContender()

        self.pub, self.sub, self.router = None, None, None  # Set in build_task_list
        self.catchup_manager = None  # This gets set at the end of build_task_list once sockets are created
        self.is_catching_up = False

        # Sanity check -- make sure StorageDriver and StateDriver have same latest block hash
        assert StateDriver.get_latest_block_hash() == StateDriver.get_latest_block_hash(), \
            "StorageDriver latest block hash {} does not match StateDriver latest hash {}" \
            .format(StateDriver.get_latest_block_hash(), StateDriver.get_latest_block_hash())

        self.run()

    def run(self):
        self.log.info("Block Aggregator starting...")
        self.build_task_list()

        self.loop.run_until_complete(asyncio.gather(*self.tasks))

    def build_task_list(self):
        self.sub = self.manager.create_socket(
            socket_type=zmq.SUB,
            name="BA-Sub-{}".format(self.verifying_key[-4:]),
            secure=True,
            # domain="sb-contender"
        )
        self.pub = self.manager.create_socket(
            socket_type=zmq.PUB,
            name="BA-Pub-{}".format(self.verifying_key[-4:]),
            secure=True,
            # domain="sb-contender"
        )
        self.pub.bind(ip=self.ip, port=MASTER_PUB_PORT)

        self.router = self.manager.create_socket(
            socket_type=zmq.ROUTER,
            name="BA-Router-{}".format(self.verifying_key[-4:]),
            secure=True,
            # domain="sb-contender"
        )
        self.router.setsockopt(zmq.ROUTER_MANDATORY, 1)  # FOR DEBUG ONLY
        self.router.setsockopt(zmq.IDENTITY, self.verifying_key.encode())
        self.router.bind(ip=self.ip, port=MASTER_ROUTER_PORT)

        self.tasks.append(self.sub.add_handler(self.handle_sub_msg))
        self.tasks.append(self.router.add_handler(self.handle_router_msg))

        # Listen to delegates for sub block contenders and state update requests
        self.sub.setsockopt(zmq.SUBSCRIBE, DEFAULT_FILTER.encode())
        for vk in VKBook.get_delegates():
            self.sub.connect(vk=vk, port=DELEGATE_PUB_PORT)
            self.router.connect(vk=vk, port=DELEGATE_ROUTER_PORT)

        # Listen to masters for new block notifs and state update requests from masters/delegates
        self.sub.setsockopt(zmq.SUBSCRIBE, CATCHUP_MN_DN_FILTER.encode())
        self.sub.setsockopt(zmq.SUBSCRIBE, DEFAULT_FILTER.encode())
        for vk in VKBook.get_masternodes():
            if vk != self.verifying_key:
                self.sub.connect(vk=vk, port=MASTER_PUB_PORT)
                self.router.connect(vk=vk, port=MASTER_ROUTER_PORT)

        self.catchup_manager = CatchupManager(verifying_key=self.verifying_key, pub_socket=self.pub,
                                              router_socket=self.router, store_full_blocks=True)

    def handle_sub_msg(self, frames):
        envelope = Envelope.from_bytes(frames[-1])
        msg = envelope.message

        if isinstance(msg, SubBlockContender):
            if self.is_catching_up:
                self.log.warning("Got SBC, but i'm still catching up. Ignoring: <{}>".format(msg))
                return
            else:
                self.recv_sub_block_contender(envelope.sender, msg)

        elif isinstance(msg, NewBlockNotification):
            self.recv_new_block_notif(envelope.sender, msg)
            # TODO send this to the catchup manager

        elif isinstance(msg, SkipBlockNotification):
            self.recv_skip_block_notif(envelope.sender, msg)

        elif isinstance(msg, BlockIndexRequest):
            self.catchup_manager.recv_block_idx_req(envelope.sender, msg)

        else:
            raise Exception("BlockAggregator got message type {} from SUB socket that it does not know how to handle"
                            .format(type(msg)))

    def handle_router_msg(self, frames):
        envelope = Envelope.from_bytes(frames[-1])
        msg = envelope.message

        if isinstance(msg, BlockDataRequest):
            self.catchup_manager.recv_block_data_req(envelope.sender, msg)

        elif isinstance(msg, BlockDataReply):
            self.catchup_manager.recv_block_data_reply(msg)

        elif isinstance(msg, BlockIndexReply):
            self.catchup_manager.recv_block_idx_reply(envelope.sender, msg)

        else:
            raise Exception("BlockAggregator got message type {} from ROUTER socket that it does not know how to handle"
                            .format(type(msg)))

    def recv_sub_block_contender(self, sender_vk: str, sbc: SubBlockContender):
        self.log.info("Received a sbc with result hash {} and input hash {}".format(sbc.result_hash, sbc.input_hash))
        assert not self.is_catching_up, "We should not be receiving SBCs when we are catching up!"

        self.curr_block.add_sbc(sender_vk, sbc)
        if self.curr_block.is_consensus_reached():
            self.log.success("Consensus reached for prev hash {}!".format(self.curr_block_hash))
            self.store_full_block()
        else:
            self.log.debugv("Consensus not reached yet.")

    def store_full_block(self):
        if self.curr_block.is_empty():
            self.log.success2("Got consensus on empty block! Sending skip block notification")
            self.send_skip_block_notif()

        else:
            # TODO wrap storage in try/catch. Add logic for storage failure
            sb_data = self.curr_block.get_sb_data()
            block_data = StorageDriver.store_block(sb_data)

            assert block_data.prev_block_hash == self.curr_block_hash, \
                "Current block hash {} does not match StorageDriver previous block hash {}"\
                .format(self.curr_block_hash, block_data.prev_block_hash)

            self.curr_block_hash = block_data.block_hash
            StateDriver.update_with_block(block_data)
            self.log.success2("STORED BLOCK WITH HASH {}".format(block_data.block_hash))
            self.send_new_block_notif(block_data)

        self.curr_block = BlockContender()  # Reset BlockContender (will this leak memory???)

    def send_new_block_notif(self, block_data: BlockData):
        new_block_notif = NewBlockNotification.create_from_block_data(block_data)
        self.pub.send_msg(msg=new_block_notif, header=DEFAULT_FILTER.encode())
        block_hash = block_data.block_hash
        self.log.info('Published new block notif with hash "{}"'.format(block_hash))

        # return new_block_notif

    def send_skip_block_notif(self):
        skip_notif = SkipBlockNotification.create(prev_block_hash=self.curr_block_hash)
        self.pub.send_msg(msg=skip_notif, header=DEFAULT_FILTER.encode())
        self.log.info("Send skip block notification for prev hash {}".format(self.curr_block_hash))

    def recv_new_block_notif(self, sender_vk: str, notif: NewBlockNotification):
        self.log.notice("MN got new block notification: {}".format(notif))
        # TODO implement

    def recv_skip_block_notif(self, sender_vk: str, notif: SkipBlockNotification):
        self.log.info("MN got new block notification: {}".format(notif))
        # TODO implement

