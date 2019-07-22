from cilantro_ee.logger.base import get_logger
from cilantro_ee.protocol.multiprocessing.worker import Worker

from cilantro_ee.storage.state import MetaDataStorage
from cilantro_ee.storage.vkbook import PhoneBook
from cilantro_ee.nodes.catchup import CatchupManager
from cilantro_ee.nodes.masternode.block_contender import BlockContender
from cilantro_ee.storage.master import CilantroStorageDriver
from cilantro_ee.constants.zmq_filters import *
from cilantro_ee.constants.ports import MN_ROUTER_PORT, MN_PUB_PORT, DELEGATE_PUB_PORT, SS_PUB_PORT
from cilantro_ee.constants.system_config import *
from cilantro_ee.constants.masternode import *
from cilantro_ee.messages.base import base
from cilantro_ee.utils.utils import int_to_bytes
from cilantro_ee.messages.envelope.envelope import Envelope
from cilantro_ee.messages.consensus.sub_block_contender import SubBlockContender
from cilantro_ee.messages.block_data.sub_block import SubBlock
from cilantro_ee.messages.block_data.state_update import *
from cilantro_ee.messages.block_data.notification import NewBlockNotification, SkipBlockNotification, FailedBlockNotification
from cilantro_ee.messages.signals.master import NonEmptyBlockMade
from cilantro_ee.messages.signals.node import Ready
from cilantro_ee.utils.utils import int_to_bytes, bytes_to_int
from cilantro_ee.contracts.sync import sync_genesis_contracts

from typing import List

import math, asyncio, zmq, time


class BlockAggregator(Worker):

    def __init__(self, ip, ipc_ip, ipc_port, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = get_logger("BlockAggregator[{}]".format(self.verifying_key[:8]))
        self.ip = ip
        self.ipc_ip = ipc_ip
        self.ipc_port = ipc_port

        self.state = MetaDataStorage()

        self.curr_block = BlockContender()

        self.pub, self.sub, self.router, self.ipc_router = None, None, None, None  # Set in build_task_list
        self.catchup_manager = None  # This gets set at the end of build_task_list once sockets are created
        self.timeout_fut = None

        self._is_catchup_done = False

        self.min_quorum = PhoneBook.delegate_quorum_min
        self.max_quorum = PhoneBook.delegate_quorum_max
        self.cur_quorum = 0

        self.curr_block_hash = self.state.get_latest_block_hash()
        # Sanity check -- make sure StorageDriver and StateDriver have same latest block hash
        # STOP COMMENTING THIS OUT PLEASE --davis

        self.driver = CilantroStorageDriver(key=self.signing_key)

        last_block = self.driver.get_last_n(1, CilantroStorageDriver.INDEX)[0]
        latest_hash = last_block.get('blockHash')
        latest_num = last_block.get('blockNum')

        # This assertion is pointless. Redis is not consistent.
        # assert latest_hash == self.state.latest_block_hash, \
        #     "StorageDriver latest block hash {} does not match StateDriver latest hash {}" \
        #     .format(latest_hash, self.state.latest_block_hash)

        self.state.latest_block_num = latest_num
        self.state.latest_block_hash = latest_hash

        self.run()

    def run(self):
        self.log.info("Block Aggregator starting...")
        self.build_task_list()

        self.loop.run_until_complete(asyncio.gather(*self.tasks))

    def build_task_list(self):
        # Create ROUTER socket for communication with batcher over IPC
        self.ipc_router = self.manager.create_socket(socket_type=zmq.ROUTER, name="BA-IPC-Router")
        self.ipc_router.bind(port=self.ipc_port, protocol='ipc', ip=self.ipc_ip)

        self.sub = self.manager.create_socket(
            socket_type=zmq.SUB,
            name="BA-Sub",
            secure=True,
        )
        self.sub.setsockopt(zmq.SUBSCRIBE, BLOCK_IDX_REQ_FILTER.encode())
        self.sub.setsockopt(zmq.SUBSCRIBE, DEFAULT_FILTER.encode())
        self.sub.setsockopt(zmq.SUBSCRIBE, NEW_BLK_NOTIF_FILTER.encode())

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

        self.catchup_manager = CatchupManager(verifying_key=self.verifying_key, signing_key=self.signing_key, pub_socket=self.pub,
                                              router_socket=self.router, store_full_blocks=True)

        self.tasks.append(self._connect_and_process())

    async def _connect_and_process(self):
        # first make sure, we have overlay server ready
        await self._wait_until_ready()

        self.log.info('connecting to masters: {}'.format(PhoneBook.masternodes))
        self.log.info('connecting to delegates: {}'.format(PhoneBook.delegates))

        # Listen to masters for _new block notifs and state update requests from masters/delegates
        for vk in PhoneBook.masternodes:
            if vk != self.verifying_key:
                self.sub.connect(vk=vk, port=MN_PUB_PORT)
                # self.router.connect(vk=vk, port=MN_ROUTER_PORT)  # we don't want 2 simultaneous look ups @ overlay server

        # Listen to delegates for sub block contenders and state update requests
        for vk in PhoneBook.delegates:
            self.sub.connect(vk=vk, port=DELEGATE_PUB_PORT)
            # I dont think we to connect to delegates to router here as delegates are already connecting
            # in BlockManager --davis
            # self.router.connect(vk=vk, port=DELEGATE_ROUTER_PORT)

        for vk in PhoneBook.schedulers + PhoneBook.notifiers:
            self.sub.connect(vk=vk, port=SS_PUB_PORT)

        # Listen to masters for new block notifs and state update requests from masters/delegates
        for vk in PhoneBook.masternodes:
            if vk != self.verifying_key:
                self.router.connect(vk=vk, port=MN_ROUTER_PORT)

        # we just connected to other nodes, let's chill a bit to give time for those connections form !!!

        # Do a dealer / router socket pair here instead.
        self.log.info("Sleeping before triggering catchup...")
        await asyncio.sleep(8)

        num_delegates_joined = self.manager.get_and_reset_num_delegates_joined()
        # assert num_delegates_joined >= self.min_quorum, "Don't have minimum quorum"
        if num_delegates_joined >= self.max_quorum:
            self.cur_quorum = self.max_quorum
        else:
            cq = math.ceil(9 * num_delegates_joined / 10)
            self.cur_quorum = max(cq, self.min_quorum)

        # now start the catchup
        await self._trigger_catchup()

    async def _trigger_catchup(self):
        self.log.info("Triggering catchup")
        # Add genesis contracts to state db if needed
        sync_genesis_contracts()

        self.catchup_manager.run_catchup()

    def _send_msg_over_ipc(self, message):
        """
        Convenience method to send a MessageBase instance over IPC router socket to a particular SBB process. Includes a
        frame to identify the type of message
        """
        if isinstance(message, MessageBase):
            id_frame = str(0).encode()
            message_type = MessageBase.registry[type(message)]  # this is an int (enum) denoting the class of message

            self.ipc_router.send_multipart([id_frame, int_to_bytes(message_type), message.serialize()])

        elif isinstance(message, base.Signal):
            id_frame = str(0).encode()
            signal_type = base.SIGNAL_VALUES[type(message)]
            self.log.spam("Message being sent via signal {}".format([id_frame, int_to_bytes(signal_type), b'']))
            self.ipc_router.send_multipart([id_frame, int_to_bytes(signal_type), b''])

    def handle_sub_msg(self, frames):
        envelope = Envelope.from_bytes(frames[-1])
        msg = envelope.message
        sender = envelope.sender

        #msg_type = bytes_to_int(frames[0])
        #msg_blob = frames[1]
        #msg = MessageBase.registry[msg_type].from_bytes(msg_blob)

        if isinstance(msg, SubBlockContender):
            if not self.catchup_manager.is_catchup_done():
                self.log.info("Got SBC, but i'm still catching up. Ignoring: <{}>".format(msg))
            else:
                self.recv_sub_block_contender(sender, msg)

        # SIGNAL
        elif isinstance(msg, NewBlockNotification) or isinstance(msg, SkipBlockNotification):
            self.recv_new_block_notif(sender, msg)

        # SIGNAL
        elif isinstance(msg, FailedBlockNotification):
            self.recv_fail_block_notif(sender, msg)

        # DATA
        elif isinstance(msg, BlockIndexRequest):
            self.catchup_manager.recv_block_idx_req(sender, msg)

        # SIGNAL
        elif not isinstance(msg, Ready):
            raise Exception("BlockAggregator got message type {} from SUB socket that it does not know how to handle"
                            .format(type(msg)))

    def _set_catchup_done(self):
        if not self._is_catchup_done:
            self._is_catchup_done = True
            self.curr_block_hash = self.state.get_latest_block_hash()
            self.curr_block.reset()
            message = Ready.create()
            self._send_msg_over_ipc(message=message)
            time.sleep(3)
            self.pub.send_msg(msg=message, header=DEFAULT_FILTER.encode())

    def handle_router_msg(self, frames):
        envelope = Envelope.from_bytes(frames[-1])
        msg = envelope.message
        sender = envelope.sender

        assert sender.encode() == frames[0], "Sender vk {} does not match id frame {}".format(sender.encode(), frames[0])

        if isinstance(msg, BlockDataRequest):
            self.catchup_manager.recv_block_data_req(sender, msg)

        elif isinstance(msg, BlockDataReply):
            if self.catchup_manager.recv_block_data_reply(msg):
                self._set_catchup_done()

        elif isinstance(msg, BlockIndexReply):
            if self.catchup_manager.recv_block_idx_reply(sender, msg):
                self._set_catchup_done()

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

        if self.curr_block.is_consensus_reached() or \
           self.curr_block.get_current_quorum_reached() >= self.cur_quorum:
            self.log.spam("currnt quorum {} actual quorum {} max quorum {}".
                          format(self.cur_quorum, self.curr_block.get_current_quorum_reached(), self.max_quorum))
            self.log.success("Consensus reached for prev hash {} (is_empty={})"
                             .format(self.curr_block_hash, self.curr_block.is_empty()))
            self.store_full_block()
            num_delegates_joined = self.manager.get_and_reset_num_delegates_joined()
            self.cur_quorum = min(self.cur_quorum + num_delegates_joined, self.max_quorum)
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
            self.log.debug("Storing a block: {}".format(self.curr_block_hash))

            try:
                block_data = self.driver.store_block(sb_data)
                self.log.debug(block_data)
            except Exception as e:
                self.log.error(str(e))

            assert block_data.prev_block_hash == self.curr_block_hash, \
                "Current block hash {} does not match StorageDriver previous block hash {}"\
                .format(self.curr_block_hash, block_data.prev_block_hash)

            self.curr_block_hash = block_data.block_hash
            self.log.info('New block incoming: {}'.format(block_data.transactions))
            self.state.update_with_block(block_data)
            self.log.success2("STORED BLOCK WITH HASH {}".format(block_data.block_hash))
            self.send_new_block_notif(block_data)

        # TODO
        # @tejas yo why does this assertion not pass? The storage driver is NOT updating its block hash after storing!
        # assert StorageDriver.get_latest_block_hash() == self.state.get_latest_block_hash(), \
        #     "StorageDriver latest block hash {} does not match StateDriver latest hash {}" \
        #         .format(StorageDriver.get_latest_block_hash(), self.state.get_latest_block_hash())

        self._reset_curr_block()

    def send_new_block_notif(self, block_data: BlockData):
        message = NonEmptyBlockMade.create()
        self._send_msg_over_ipc(message=message)
        new_block_notif = NewBlockNotification.create(block_data.prev_block_hash,
                               block_data.block_hash, block_data.block_num,
                               block_data.sub_blocks[0].index,
                               block_data.block_owners, block_data.input_hashes)
        # sleep a bit so slower nodes don't have to constantly use catchup mgr 
        time.sleep(0.1)
        self.pub.send_msg(msg=new_block_notif, header=NEW_BLK_NOTIF_FILTER.encode())
        self.log.info('Published new block notif with hash "{}" and prev hash {}'
                      .format(block_data.block_hash, block_data.prev_block_hash))

    def send_skip_block_notif(self, sub_blocks: List[SubBlock]):
        # until we have proper async way to control the speed of network, we use this crude method to control the speed
        time.sleep(30)

        # SIGNAL
        #message = EmptyBlockMade.create()
        message = base.EmptyBlockMade()
        self._send_msg_over_ipc(message=message)


        skip_notif = SkipBlockNotification.create_from_sub_blocks(self.curr_block_hash,
                                  self.state.latest_block_num+1, [], sub_blocks)


        self.pub.send_msg(msg=skip_notif, header=DEFAULT_FILTER.encode())
        self.log.debugv("Send skip block notification for prev hash {}".format(self.curr_block_hash))

    def send_fail_block_notif(self):
        msg = self.curr_block.get_failed_block_notif()
        self.log.debugv("Sending failed block notif {}".format(msg))
        self.pub.send_msg(msg=msg, header=DEFAULT_FILTER.encode())

    def recv_new_block_notif(self, sender_vk: str, notif: NewBlockNotification):
        self.log.debugv("MN got new block notification: {}".format(notif))

        if notif.block_num > self.state.latest_block_num + 1:
            self.log.info("Block num {} on NBC does not match our block num {}! Triggering catchup".format(notif.block_num, self.state.latest_block_num))
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

            self.log.critical("Block timeout of {}s reached for block hash {}!"
                              .format(BLOCK_PRODUCTION_TIMEOUT, self.curr_block_hash))
            new_quorum = self.curr_block.get_current_quorum_reached()
            if new_quorum >= self.min_quorum and new_quorum >= (9 * self.cur_quorum // 10):
                self.log.warning("Reducing consensus quorum from {} to {}".
                          format(self.curr_block.get_current_quorum_reached(), new_quorum))
                self.store_full_block()
                self.cur_quorum = new_quorum
            else:
                self.log.debugv("sending fail block notif")
                self.send_fail_block_notif()
            self.curr_block.reset()
            num_delegates_joined = self.manager.get_and_reset_num_delegates_joined()
            self.cur_quorum = min(self.cur_quorum + num_delegates_joined, self.max_quorum)
        except asyncio.CancelledError:
            pass

    def _reset_curr_block(self):
        self.curr_block.reset()
        self.log.debugv("Canceling block timeout")
        if self.timeout_fut and not self.timeout_fut.done():
            self.timeout_fut.cancel()


