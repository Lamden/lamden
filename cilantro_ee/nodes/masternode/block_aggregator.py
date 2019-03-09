from cilantro_ee.logger.base import get_logger
from cilantro_ee.protocol.multiprocessing.worker import Worker
from cilantro_ee.protocol.structures.merkle_tree import MerkleTree

from cilantro_ee.storage.state import StateDriver
from cilantro_ee.storage.vkbook import VKBook
from cilantro_ee.nodes.catchup import CatchupManager
from cilantro_ee.nodes.masternode.mn_api import StorageDriver
from cilantro_ee.nodes.masternode.block_contender import BlockContender

from cilantro_ee.constants.zmq_filters import *
from cilantro_ee.constants.ports import MN_ROUTER_PORT, MN_PUB_PORT, DELEGATE_PUB_PORT
from cilantro_ee.constants.system_config import *
from cilantro_ee.constants.masternode import *

from cilantro_ee.utils.utils import int_to_bytes, bytes_to_int
from cilantro_ee.messages.envelope.envelope import Envelope
from cilantro_ee.messages.consensus.sub_block_contender import SubBlockContender
from cilantro_ee.messages.consensus.merkle_signature import MerkleSignature
from cilantro_ee.messages.block_data.block_data import BlockData
from cilantro_ee.messages.block_data.sub_block import SubBlock
from cilantro_ee.messages.block_data.state_update import *
from cilantro_ee.messages.block_data.block_metadata import NewBlockNotification, SkipBlockNotification
from cilantro_ee.messages.signals.master import EmptyBlockMade, NonEmptyBlockMade
from cilantro_ee.messages.transaction.data import TransactionData

from cilantro_ee.utils.hasher import Hasher
from cilantro_ee.protocol import wallet
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

        self.curr_block = BlockContender()

        self.pub, self.sub, self.router, self.ipc_router = None, None, None, None  # Set in build_task_list
        self.catchup_manager = None  # This gets set at the end of build_task_list once sockets are created
        self.timeout_fut = None

        self.curr_block_hash = StateDriver.get_latest_block_hash()
        # Sanity check -- make sure StorageDriver and StateDriver have same latest block hash
        # STOP COMMENTING THIS OUT PLEASE --davis
        assert StorageDriver.get_latest_block_hash() == StateDriver.get_latest_block_hash(), \
            "StorageDriver latest block hash {} does not match StateDriver latest hash {}" \
            .format(StorageDriver.get_latest_block_hash(), StateDriver.get_latest_block_hash())

        self.run()

    def run(self):
        self.log.info("Block Aggregator starting...")
        self.build_task_list()

        self.loop.run_until_complete(asyncio.gather(*self.tasks))

    def build_task_list(self):
        self.sub = self.manager.create_socket(
            socket_type=zmq.SUB,
            name="BA-Sub",
            secure=True,
        )
        self.pub = self.manager.create_socket(
            socket_type=zmq.PUB,
            name="BA-Pub",
            secure=True,
        )
        self.pub.bind(ip=self.ip, port=MN_PUB_PORT)

        self.router = self.manager.create_socket(
            socket_type=zmq.ROUTER,
            name="BA-Router",
            secure=True,
        )
        self.router.setsockopt(zmq.IDENTITY, self.verifying_key.encode())
        self.router.bind(ip=self.ip, port=MN_ROUTER_PORT)

        self.tasks.append(self.sub.add_handler(self.handle_sub_msg))
        self.tasks.append(self.router.add_handler(self.handle_router_msg))

        self.catchup_manager = CatchupManager(verifying_key=self.verifying_key, pub_socket=self.pub,
                                              router_socket=self.router, store_full_blocks=True)

        # Create ROUTER socket for communication with batcher over IPC
        self.ipc_router = self.manager.create_socket(socket_type=zmq.ROUTER, name="BA-IPC-Router")
        self.ipc_router.bind(port=self.ipc_port, protocol='ipc', ip=self.ipc_ip)

        self.tasks.append(self._connect_and_process())


    async def _connect_and_process(self):
        # first make sure, we have overlay server ready
        await self._wait_until_ready()

        # Listen to masters for new block notifs and state update requests from masters/delegates
        self.sub.setsockopt(zmq.SUBSCRIBE, CATCHUP_MN_DN_FILTER.encode())
        for vk in VKBook.get_masternodes():
            if vk != self.verifying_key:
                self.sub.connect(vk=vk, port=MN_PUB_PORT)
                self.router.connect(vk=vk, port=MN_ROUTER_PORT)

        # Listen to delegates for sub block contenders and state update requests
        self.sub.setsockopt(zmq.SUBSCRIBE, DEFAULT_FILTER.encode())
        for vk in VKBook.get_delegates():
            self.sub.connect(vk=vk, port=DELEGATE_PUB_PORT)
            # I dont think we to connect to delegates here as delegates are already connecting in BlockManager --davis
            # self.router.connect(vk=vk, port=DELEGATE_ROUTER_PORT)

        # we just connected to other nodes, let's chill a bit to give time for those connections form !!!
        self.log.spam("Sleeping before triggering catchup...")
        await asyncio.sleep(8)
        # now start the catchup
        await self._trigger_catchup()

    async def _trigger_catchup(self):
        self.log.info("Triggering catchup")
        self.catchup_manager.run_catchup()

    def _send_msg_over_ipc(self, message: MessageBase):
        """
        Convenience method to send a MessageBase instance over IPC router socket to a particular SBB process. Includes a
        frame to identify the type of message
        """
        self.log.spam("Sending msg to batcher: {}".format(message))
        assert isinstance(message, MessageBase), "Must pass in a MessageBase instance"
        id_frame = str(0).encode()
        message_type = MessageBase.registry[type(message)]  # this is an int (enum) denoting the class of message
        self.ipc_router.send_multipart([id_frame, int_to_bytes(message_type), message.serialize()])

    def handle_sub_msg(self, frames):
        envelope = Envelope.from_bytes(frames[-1])
        msg = envelope.message
        sender = envelope.sender
        self.log.spam("Got SUB msg from sender {}\nMessage: {}".format(sender, msg))

        if isinstance(msg, SubBlockContender):
            if not self.catchup_manager.is_catchup_done():
                self.log.info("Got SBC, but i'm still catching up. Ignoring: <{}>".format(msg))
            else:
                self.recv_sub_block_contender(sender, msg)

        elif isinstance(msg, NewBlockNotification) or isinstance(msg, SkipBlockNotification):
            self.recv_new_block_notif(sender, msg)

        elif isinstance(msg, FailedBlockNotification):
            self.recv_fail_block_notif(sender, msg)

        elif isinstance(msg, BlockIndexRequest):
            self.catchup_manager.recv_block_idx_req(sender, msg)

        else:
            raise Exception("BlockAggregator got message type {} from SUB socket that it does not know how to handle"
                            .format(type(msg)))

    def handle_router_msg(self, frames):
        envelope = Envelope.from_bytes(frames[-1])
        msg = envelope.message
        sender = envelope.sender

        assert sender.encode() == frames[0], "Sender vk {} does not match id frame {}".format(sender.encode(), frames[0])
        self.log.spam("Got ROUTER msg from sender {} with id frame {}\nMessage: {}".format(sender, frames[0], msg))

        if isinstance(msg, BlockDataRequest):
            self.catchup_manager.recv_block_data_req(sender, msg)

        elif isinstance(msg, BlockDataReply):
            if self.catchup_manager.recv_block_data_reply(msg):
                self.curr_block_hash = StateDriver.get_latest_block_hash()
                self.curr_block.reset()

        elif isinstance(msg, BlockIndexReply):
            if self.catchup_manager.recv_block_idx_reply(sender, msg):
                self.curr_block_hash = StateDriver.get_latest_block_hash()
                self.curr_block.reset()

        else:
            raise Exception("BlockAggregator got message type {} from ROUTER socket that it does not know how to handle"
                            .format(type(msg)))

    def recv_sub_block_contender(self, sender_vk: str, sbc: SubBlockContender):
        self.log.debugv("Received a sbc from sender {} with result hash {} and input hash {}"
                        .format(sender_vk, sbc.result_hash, sbc.input_hash))

        added_first_sbc = self.curr_block.add_sbc(sender_vk, sbc)
        if added_first_sbc:
            self.log.debug("First SBC receiver for prev block hash {}! Scheduling timeout".format(self.curr_block_hash))
            self.timeout_fut = asyncio.ensure_future(self.schedule_block_timeout())

        if self.curr_block.is_consensus_reached():
            self.log.success("Consensus reached for prev hash {} (is_empty={})"
                             .format(self.curr_block_hash, self.curr_block.is_empty()))
            self.store_full_block()
            return

        if not self.curr_block.is_consensus_possible():
            self.log.critical("Consensus not possible for prev block hash {}! Sending failed block notif".format(self.curr_block_hash))
            self.send_fail_block_notif()
            self._reset_curr_block()
        else:
            self.log.debugv("Consensus not reached yet.")

    def store_full_block(self):
        sb_data = self.curr_block.get_sb_data()
        if self.curr_block.is_empty():
            self.log.debug("Got consensus on empty block with prev hash {}! Sending skip block notification".format(self.curr_block_hash))
            self.send_skip_block_notif(sb_data)

        else:
            # TODO wrap storage in try/catch. Add logic for storage failure
            block_data = StorageDriver.store_block(sb_data)

            assert block_data.prev_block_hash == self.curr_block_hash, \
                "Current block hash {} does not match StorageDriver previous block hash {}"\
                .format(self.curr_block_hash, block_data.prev_block_hash)

            self.curr_block_hash = block_data.block_hash
            StateDriver.update_with_block(block_data)
            self.log.success2("STORED BLOCK WITH HASH {}".format(block_data.block_hash))
            self.send_new_block_notif(block_data)

        # TODO
        # @tejas yo why does this assertion not pass? The storage driver is NOT updating its block hash after storing!
        # assert StorageDriver.get_latest_block_hash() == StateDriver.get_latest_block_hash(), \
        #     "StorageDriver latest block hash {} does not match StateDriver latest hash {}" \
        #         .format(StorageDriver.get_latest_block_hash(), StateDriver.get_latest_block_hash())

        self._reset_curr_block()

    def send_new_block_notif(self, block_data: BlockData):
        message = NonEmptyBlockMade.create()
        self._send_msg_over_ipc(message=message)
        new_block_notif = NewBlockNotification.create_from_block_data(block_data)
        # sleep a bit so slower nodes don't have to constantly use catchup mgr 
        time.sleep(0.1)
        self.pub.send_msg(msg=new_block_notif, header=DEFAULT_FILTER.encode())
        self.log.info('Published new block notif with hash "{}" and prev hash {}'
                      .format(block_data.block_hash, block_data.prev_block_hash))

    def send_skip_block_notif(self, sub_blocks: List[SubBlock]):
        message = EmptyBlockMade.create()
        self._send_msg_over_ipc(message=message)
        skip_notif = SkipBlockNotification.create_from_sub_blocks(self.curr_block_hash, StateDriver.get_latest_block_num()+1, sub_blocks)
        self.pub.send_msg(msg=skip_notif, header=DEFAULT_FILTER.encode())
        self.log.debugv("Send skip block notification for prev hash {}".format(self.curr_block_hash))

    def send_fail_block_notif(self):
        msg = self.curr_block.get_failed_block_notif()
        self.pub.send_msg(msg=msg, header=DEFAULT_FILTER.encode())
        self.log.debug("Uh oh! Sending failed block notif {}".format(msg))

    def recv_new_block_notif(self, sender_vk: str, notif: NewBlockNotification):
        self.log.debugv("MN got new block notification: {}".format(notif))

        if notif.block_num > StateDriver.get_latest_block_num() + 1:
            self.log.info("Block num {} on NBC does not match our block num {}! Triggering catchup".format(notif.block_num, StateDriver.get_latest_block_num()))
            self.catchup_manager.recv_new_blk_notif(notif)
        else:
            self.log.debugv("Block num on NBC is LTE that ours. Ignoring")

    def recv_fail_block_notif(self, sender_vk: str, notif: FailedBlockNotification):
        self.log.debugv("MN got fail block notification: {}".format(notif))
        # TODO implement

    async def schedule_block_timeout(self):
        try:
            elapsed = 0

            while elapsed < BLOCK_PRODUCTION_TIMEOUT:
                await asyncio.sleep(BLOCK_TIMEOUT_POLL)
                elapsed += BLOCK_TIMEOUT_POLL

            self.log.critical("Block timeout of {}s reached for block hash {}! Resetting sub block contenders and sending "
                              "skip block notification.".format(BLOCK_PRODUCTION_TIMEOUT, self.curr_block_hash))
            self.send_fail_block_notif()
            self.curr_block.reset()
        except asyncio.CancelledError:
            pass

    def _reset_curr_block(self):
        self.curr_block.reset()
        self.log.debugv("Canceling block timeout")
        if self.timeout_fut and not self.timeout_fut.done():
            self.timeout_fut.cancel()


