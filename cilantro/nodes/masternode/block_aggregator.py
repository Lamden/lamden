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
from cilantro.constants.masternode import *

from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.consensus.sub_block_contender import SubBlockContender
from cilantro.messages.consensus.merkle_signature import MerkleSignature
from cilantro.messages.block_data.block_data import BlockData
from cilantro.messages.block_data.sub_block import SubBlock
from cilantro.messages.block_data.state_update import *
from cilantro.messages.block_data.block_metadata import NewBlockNotification
from cilantro.messages.signals.master import SendNextBag
from cilantro.messages.transaction.data import TransactionData

from cilantro.utils.hasher import Hasher
from cilantro.protocol import wallet
from typing import List

import asyncio, zmq, os, time, itertools
from collections import defaultdict


class BlockAggregator(Worker):

    def __init__(self, ip, ipc_ip, ipc_port, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = get_logger("BlockAggregator[{}]".format(self.verifying_key[:8]))
        self.ip = ip
        self.ipc_ip = ipc_ip
        self.ipc_port = ipc_port

        self.tasks = []

        self.curr_block_hash = StateDriver.get_latest_block_hash()
        self.curr_block = BlockContender()

        self.pub, self.sub, self.router, self.ipc_router = None, None, None, None  # Set in build_task_list
        self.catchup_manager = None  # This gets set at the end of build_task_list once sockets are created
        self.timeout_fut = None
        self.num_empty_blocks = 0

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

        # Create ROUTER socket for communication with batcher over IPC
        self.ipc_router = self.manager.create_socket(socket_type=zmq.ROUTER, name="BA-IPC-Router")
        self.ipc_router.setsockopt(zmq.ROUTER_MANDATORY, 1)  # FOR DEBUG ONLY
        self.ipc_router.bind(port=self.ipc_port, protocol='ipc', ip=self.ipc_ip)
        # self.tasks.append(self.ipc_router.add_handler(self.handle_ipc_msg))

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

     
    def _send_msg_over_ipc(self, message: MessageBase):
        """
        Convenience method to send a MessageBase instance over IPC router socket to a particular SBB process. Includes a
        frame to identify the type of message
        """
        self.log.spam("Sending msg to batcher")
        assert isinstance(message, MessageBase), "Must pass in a MessageBase instance"
        id_frame = str(0).encode()
        message_type = MessageBase.registry[type(message)]  # this is an int (enum) denoting the class of message
        self.ipc_router.send_multipart([id_frame, int_to_bytes(message_type), message.serialize()])


    def handle_ipc_msg(self, frames):
        self.log.spam("BA got msg over Dealer IPC with frames: {}".format(frames))
        assert len(frames) == 2, "Expected 2 frames: (msg_type, msg_blob). Got {} instead.".format(frames)

        msg_type = bytes_to_int(frames[0])
        msg_blob = frames[1]

        msg = MessageBase.registry[msg_type].from_bytes(msg_blob)
        self.log.debugv("BA received an IPC message {}".format(msg))

        if isinstance(msg, SendNextBag):
            self.log.important2("Really, I got this one!!!")

        self.log.important2("Why did I get this one and from whom?")

    def handle_sub_msg(self, frames):
        envelope = Envelope.from_bytes(frames[-1])
        msg = envelope.message

        if isinstance(msg, SubBlockContender):
            if self.catchup_manager.catchup_state:
                self.log.info("Got SBC, but i'm still catching up. Ignoring: <{}>".format(msg))
            else:
                self.recv_sub_block_contender(envelope.sender, msg)

        elif isinstance(msg, NewBlockNotification):
            if self.catchup_manager.catchup_state:
                self.catchup_manager.recv_new_blk_notif(msg)
            else:
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
        assert not self.catchup_manager.catchup_state, "We should not be receiving SBCs when we are catching up!"
        self.log.debugv("Received a sbc with result hash {} and input hash {}".format(sbc.result_hash, sbc.input_hash))

        added_first_sbc = self.curr_block.add_sbc(sender_vk, sbc)
        if added_first_sbc:
            self.log.debug("First SBC receiver for prev block hash {}! Scheduling timeout".format(self.curr_block_hash))
            self.timeout_fut = asyncio.ensure_future(self.schedule_block_timeout())

        if self.curr_block.is_consensus_reached():
            self.log.info("Consensus reached for prev hash {}!".format(self.curr_block_hash))
            self.store_full_block()
            return

        if not self.curr_block.is_consensus_possible():
            self.log.critical("Consensus not possible for prev block hash {}! Sending skip block notif".format(self.curr_block_hash))
            self.send_skip_block_notif()
        else:
            self.log.debugv("Consensus not reached yet.")

    def store_full_block(self):
        self.log.debugv("Canceling block timeout")
        self.timeout_fut.cancel()

        if self.curr_block.is_empty():
            self.log.debug("Got consensus on empty block with prev hash {}! Sending skip block notification".format(self.curr_block_hash))
            self.num_empty_blocks = self.num_empty_blocks + 1
            if self.num_empty_blocks >= NUM_BLOCKS:
                time.sleep(NO_ACTIVITY_SLEEP)
            self.send_skip_block_notif()

        else:
            self.num_empty_blocks = 0
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

    def send_block_notif(self, block_data: MessageBase):
        self.pub.send_msg(msg=block_data, header=DEFAULT_FILTER.encode())
        message = SendNextBag.create()
        self._send_msg_over_ipc(message=message)

    def send_new_block_notif(self, block_data: BlockData):
        new_block_notif = NewBlockNotification.create_from_block_data(block_data)
        self.send_block_notif(new_block_notif)
        # self.pub.send_msg(msg=new_block_notif, header=DEFAULT_FILTER.encode())
        self.log.info('Published new block notif with hash "{}" and prev hash {}'
                      .format(block_data.block_hash, block_data.prev_block_hash))

    def send_skip_block_notif(self):
        skip_notif = SkipBlockNotification.create(prev_block_hash=self.curr_block_hash)
        self.send_block_notif(skip_notif)
        # self.pub.send_msg(msg=skip_notif, header=DEFAULT_FILTER.encode())
        self.log.debugv("Send skip block notification for prev hash {}".format(self.curr_block_hash))

    def recv_new_block_notif(self, sender_vk: str, notif: NewBlockNotification):
        self.log.debugv("MN got new block notification: {}".format(notif))
        # TODO implement

    def recv_skip_block_notif(self, sender_vk: str, notif: SkipBlockNotification):
        self.log.debugv("MN got new block notification: {}".format(notif))
        # TODO implement

    async def schedule_block_timeout(self):
        elapsed = 0

        while elapsed < BLOCK_PRODUCTION_TIMEOUT:
            await asyncio.sleep(BLOCK_TIMEOUT_POLL)
            elapsed += BLOCK_TIMEOUT_POLL

        self.log.critical("Block timeout of {}s reached for block hash {}! Resetting sub block contenders and sending "
                          "skip block notification.".format(BLOCK_PRODUCTION_TIMEOUT, self.curr_block_hash))
        self.send_skip_block_notif()
        self.curr_block = BlockContender()



