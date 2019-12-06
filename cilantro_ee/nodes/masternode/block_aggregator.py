from cilantro_ee.core.logger.base import get_logger
from cilantro_ee.core.utils.worker import Worker

from cilantro_ee.services.storage.state import MetaDataStorage
from cilantro_ee.nodes.masternode.block_contender import BlockContender
from cilantro_ee.services.storage.master import CilantroStorageDriver
from cilantro_ee.constants.zmq_filters import *
from cilantro_ee.constants.ports import MN_ROUTER_PORT, MN_PUB_PORT, DELEGATE_PUB_PORT, SS_PUB_PORT
from cilantro_ee.constants.system_config import *
from cilantro_ee.constants.masternode import *
from cilantro_ee.core.messages.notification import BlockNotification
from cilantro_ee.contracts.sync import sync_genesis_contracts
from cilantro_ee.core.messages.message_type import MessageType
from cilantro_ee.core.messages.message import Message
from cilantro_ee.services.block_fetch import BlockFetcher
from cilantro_ee.services.storage.vkbook import VKBook
import math
import asyncio
import zmq
import time
from contextlib import suppress

import zmq.asyncio
from cilantro_ee.core.sockets.services import SocketStruct, SubscriptionService


class BlockKind:
    NEW_BLOCK = 0
    EMPTY_BLOCK = 1
    FAILED_BLOCK = 2


# Publishes block notifications to people
class BlockNotifier:
    def __init__(self, wallet, socket_struct, ctx: zmq.asyncio.Context()):
        self.wallet = wallet
        self.socket_struct = socket_struct
        self.ctx = ctx
        self.socket = self.ctx.socket(zmq.PUB)
        self.socket.bind(str(socket_struct))

    def send_ready(self):
        # Construct a cryptographically signed message of the current time such that the receiver can verify it
        mtype, msg = Message.get_signed_message_packed(
            wallet=self.wallet,
            msg_type=MessageType.READY)

        self.socket.send_msg(msg=msg, msg_type=mtype,
                          filter=DEFAULT_FILTER.encode())

    def send_block_notif(self, block_num, block_hash, block_owners, first_sb_idx, input_hashes, kind):
        arguments = {
            'blockNum': block_num,
            'blockHash': block_hash,
            'blockOwners': block_owners,
            'firstSbIdx': first_sb_idx,
            'inputHashes': input_hashes,
        }

        # This looks odd because it is preparing to set a Capnp Union which behaves in a way Python does not support
        if kind == BlockKind.NEW_BLOCK:
            arguments['newBlock'] = None
        elif kind == BlockKind.EMPTY_BLOCK:
            arguments['emptyBlock'] = None
        else:
            arguments['failedBlock'] = None

        mtype, bn = Message.get_signed_message_packed(
            wallet=self.wallet,
            msg_type=MessageType.BLOCK_NOTIFICATION,
            **arguments)

        # clean up filters for different block notifications - unify it under BLK_NOTIF_FILTER ?
        self.socket.send_msg(filter=DEFAULT_FILTER.encode(), msg_type=mtype, msg=bn)


# Sends this to Transaction Batcher
class TransactionBatcherInformer:
    def __init__(self, socket_id):
        self.ipc_router = None

    def send_ready(self):
        mtype, msg = Message.get_message_packed(MessageType.READY)
        self.ipc_router.send_multipart([b'0', mtype, msg])

    def send_burn_input_hashes(self, hashes):
        bih_mtype, bih = Message.get_message_packed(MessageType.BURN_INPUT_HASHES, inputHashes=hashes)
        self.ipc_router.send_multipart([b'0', bih_mtype, bih])


class BlockBuilder:
    def __init__(self, current_quorum, block_timeout):
        self.current_quorum = current_quorum
        self.block_timeout = block_timeout

        self.block = BlockContender()

        self.failed = False
        self.done = False

        self.timeout = None

    def quorum_reached(self):
        return self.block.get_current_quorum_reached()

    def add_subblock_contender(self, sender, msg):
        added_first_sbc = self.block.add_sbc(sender, msg)

        if added_first_sbc:
            self.timeout = asyncio.ensure_future(self.block_timeout())

        if self.block.is_consensus_reached() or self.block.get_current_quorum_reached() >= self.current_quorum:
            self.done = True
            self.timeout.cancel()

        elif not self.block.is_consensus_possible():
            self.failed = True
            self.timeout.cancel()

    async def block_timeout(self):
        with suppress(asyncio.CancelledError):
            await asyncio.sleep(BLOCK_PRODUCTION_TIMEOUT)
            self.try_quorum_adjustment()
            self.cleanup_full_block_failure()

    def try_quorum_adjustment(self):
        new_quorum = self.curr_block.get_current_quorum_reached()

        if new_quorum >= PhoneBook.delegate_quorum_min and new_quorum >= (9 * self.current_quorum // 10):
            self.store_full_block()
            self.reset()
            self.current_quorum = new_quorum

        else:
            self.log.debugv("sending fail block notif")
            self.send_fail_block_notif()


class SubBlockBuilderSubscriber(SubscriptionService):
    def __init__(self, masternode_sockets, delegate_sockets, state: MetaDataStorage, ctx: zmq.Context, timeout=100, linger=2000):
        super().__init__(ctx=ctx, timeout=timeout, linger=linger)

        self.masternodes = masternode_sockets
        self.delegates = delegate_sockets

        for master in self.masternodes.sockets.values():
            self.add_subscription(master)

        for delegate in self.delegates.sockets.values():
            self.add_subscription(delegate)

        self.state = state

        self.fetcher = BlockFetcher()

        self.current_block = BlockBuilder(current_quorum=0)

    async def process_received(self):
        if len(self.received) > 0:
            recv = self.received.pop(0)
            msg_filter, msg_type, msg_blob = recv

            msg_type, msg, sender, timestamp, is_verified = Message.unpack_message(msg_type, msg_blob)
            if not is_verified:
                return

            if msg_type == MessageType.SUBBLOCK_CONTENDER:
                self.process_sub_block_contender(sender, msg)

            elif msg_type == MessageType.BLOCK_NOTIFICATION:
                self.process_new_block_notification(sender, msg)

    def process_sub_block_contender(self, sender, msg):
        pass

    def process_new_block_notification(self, sender, msg):
        self.log.debugv("MN got new block notification: {}".format(msg))

        blocknum = msg.blockNum

        if (blocknum > self.state.latest_block_num + 1) and \
                (msg.type.which() == "newBlock"):
            self.fetcher.intermediate_sync(msg)


class BlockAggregator(Worker):
    def __init__(self, ip, ipc_ip, ipc_port, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = get_logger("BlockAggregator[{}]".format(self.verifying_key[:8]))
        self.vkbook = VKBook()

        assert self.verifying_key in self.vkbook.masternodes, "not a part of VKBook"

        self.ip = ip
        self.ipc_ip = ipc_ip
        self.ipc_port = ipc_port

        self.state = MetaDataStorage()

        self.curr_block = BlockContender()

        self.pub, self.sub, self.router, self.ipc_router = None, None, None, None  # Set in build_task_list

        self.timeout_fut = None

        self._is_catchup_done = False

        self.min_quorum = self.vkbook.delegate_quorum_min
        self.max_quorum = self.vkbook.delegate_quorum_max
        self.cur_quorum = 0

        self.my_mn_idx = self.vkbook.masternodes.index(self.verifying_key)
        self.my_sb_idx = self.my_mn_idx % NUM_SB_BUILDERS

        self.curr_block_hash = self.state.get_latest_block_hash()

        # Should this be done somewhere else?
        self.driver = CilantroStorageDriver(key=self.signing_key)

        last_block = self.driver.get_last_n(1, CilantroStorageDriver.INDEX)[0]
        latest_hash = last_block.get('blockHash')
        latest_num = last_block.get('blockNum')

        self.state.latest_block_num = latest_num
        self.state.latest_block_hash = latest_hash
        # # #

        self.block_fetcher = BlockFetcher(wallet=self.wallet,
                                          ctx=self.zmq_ctx,
                                          blocks=self.driver,
                                          state=self.state)

        self.block_notifier = BlockNotifier(wallet=self.wallet,
                                            ctx=self.zmq_ctx,
                                            socket_struct=None)

        self.transaction_batch_informer = TransactionBatcherInformer(
            socket_id=None
        )

        self.num_delegates_joined_since_last = 0

    def adjust_quorum(self, num_delegates_joined):
        if num_delegates_joined >= self.max_quorum:
            self.cur_quorum = self.max_quorum
        else:
            cq = math.ceil(9 * num_delegates_joined / 10)
            self.cur_quorum = max(cq, self.min_quorum)

    async def _connect_and_process(self):
        # Extract this out from socket manager
        num_delegates_joined = self.manager.get_and_reset_num_delegates_joined()

        self.adjust_quorum(num_delegates_joined)

        self.log.info("Triggering catchup")
        # Add genesis contracts to state db if needed

        sync_genesis_contracts()
        await self.block_fetcher.sync()

        self.curr_block_hash = self.state.get_latest_block_hash()
        self.curr_block.reset()

        self.transaction_batch_informer.send_ready()
        self.block_notifier.send_ready()

        self.log.success('READY SIGNAL SENT TO SUBS')

### SUB MESSAGE LOOP SHOULD BE ASYNC
    def handle_sub_msg(self, frames):
        msg_filter, msg_type, msg_blob = frames
        self.log.success(len(frames))

        msg_type, msg, sender, timestamp, is_verified = Message.unpack_message(msg_type, msg_blob)
        if not is_verified:
            self.log.error("Failed to verify the message of type {} from {} at {}. Ignoring it .."
                          .format(msg_type, sender, timestamp))
            return

        # # Move this socket to where the communication is happening (IE: the blockserver?)
        # if msg_type == MessageType.BLOCK_INDEX_REQUEST:
        #     self.catchup_manager.recv_block_idx_req(msg)

        if msg_type == MessageType.SUBBLOCK_CONTENDER:
            self.recv_sub_block_contender(sender, msg)

        # Process block notification messages
        elif msg_type == MessageType.BLOCK_NOTIFICATION:
            self.log.important3(
                "BlockAGG got BlockNotification from sender {} with hash {}"
                .format(sender, msg.blockHash))
            # Process accordingly
            self.recv_new_block_notif(sender, msg)

    # Most likely testable
    def recv_sub_block_contender(self, sender_vk: str, sbc):
        self.log.debugv("Received a sbc from sender {} with result hash {} and input hash {}"
                        .format(sender_vk, sbc.resultHash, sbc.inputHash))

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

    # Very testable
    def store_full_block(self):
        sb_data = self.curr_block.get_sb_data()

        self.log.info(sb_data)

        if self.curr_block.is_empty():
            self.log.info("Got consensus on empty block with prev hash {}! Sending skip block notification".format(self.curr_block_hash))
            time.sleep(10)
            self.send_skip_block_notif(sb_data)

        else:
            # TODO wrap storage in try/catch. Add logic for storage failure
            self.log.info("Storing a block: {}".format(self.curr_block_hash))

            #try:
            block_data = self.driver.store_block(sb_data)
            self.log.debug(block_data)

            assert block_data['prevBlockHash'] == self.curr_block_hash, \
                "Current block hash {} does not match StorageDriver previous block hash {}"\
                .format(self.curr_block_hash, block_data['prevBlockHash'])

            self.curr_block_hash = block_data['blockHash']
            self.state.update_with_block(block_data)

            self.log.success2("STORED BLOCK WITH HASH {}".format(block_data['blockHash']))

            self.send_new_block_notif(block_data)

            #except Exception as e:
            #    self.log.error(str(e))

        # TODO
        # @tejas yo why does this assertion not pass? The storage blocks is NOT updating its block hash after storing!
        # assert StorageDriver.get_latest_block_hash() == self.state.get_latest_block_hash(), \
        #     "StorageDriver latest block hash {} does not match StateDriver latest hash {}" \
        #         .format(StorageDriver.get_latest_block_hash(), self.state.get_latest_block_hash())

        self._reset_curr_block()

    # Why is this kwargs? They all have the same values...
    def send_block_notif(self, msg_type, **kwargs):
        mn_idx = kwargs.get('firstSbIdx') + self.my_sb_idx
        if mn_idx == self.my_mn_idx:
            input_hashes = kwargs.get('inputHashes')
            my_input_hashes = input_hashes[self.my_sb_idx]
            self.log.info("Need to burn input bags with hash(es) {}".format(my_input_hashes))

            bih_mtype, bih = Message.get_message_packed(MessageType.BURN_INPUT_HASHES, inputHashes=my_input_hashes)
            self.ipc_router.send_multipart([b'0', bih_mtype, bih])

        mtype, bn = Message.get_signed_message_packed(
                             wallet=self.wallet,
                             msg_type=msg_type, **kwargs)

        # clean up filters for different block notifications - unify it under BLK_NOTIF_FILTER ?
        # BN = block notification
        self.pub.send_msg(filter=DEFAULT_FILTER.encode(), msg_type=mtype, msg=bn)


    def send_new_block_notif(self, block_data):
        # sleep a bit so slower nodes don't have to constantly use catchup mgr 
        time.sleep(0.1)

        # SEND NEW BLOCK NOTIFICATION on pub
        self.send_block_notif(MessageType.BLOCK_NOTIFICATION,
                              blockNum=block_data['blockNum'],
                              blockHash=block_data['blockHash'],
                              blockOwners=block_data['blockOwners'],
                              firstSbIdx=block_data['subBlocks'][0].subBlockIdx,
                              inputHashes=[[sb.inputHash] for sb in block_data['subBlocks']],
                              newBlock=None)
        self.log.info('Published new block notif with hash "{}" and block num {}'
                      .format(block_data['blockHash'], block_data['blockNum']))

    def send_skip_block_notif(self, sub_blocks):
        # assert that sub_blocks are sorted by subBlockIdx
        last_hash = self.state.latest_block_hash
        block_num = self.state.latest_block_num + 1
        input_hashes = [[sb.inputHash] for sb in sub_blocks]
        block_hash = BlockNotification.get_block_hash(last_hash, input_hashes)

        self.send_block_notif(MessageType.BLOCK_NOTIFICATION,
                              blockNum=block_num,
                              blockHash=block_hash,
                              blockOwners=[],
                              firstSbIdx=sub_blocks[0].subBlockIdx,
                              inputHashes=input_hashes,
                              emptyBlock=None)

        self.log.debugv("Published empty block notification for hash {} num {}"
                        .format(block_hash, block_num))

    def send_fail_block_notif(self):
        last_hash = self.state.latest_block_hash
        block_num = self.state.latest_block_num + 1
        input_hashes = self.curr_block.get_input_hashes_sorted()
        block_hash = BlockNotification.get_block_hash(last_hash, input_hashes)
        first_sb_idx = self.curr_block.get_first_sb_idx_sorted()

        self.send_block_notif(MessageType.BLOCK_NOTIFICATION,
                              blockNum=block_num,
                              blockHash=block_hash,
                              blockOwners=[],
                              firstSbIdx=first_sb_idx,
                              inputHashes=input_hashes,
                              failedBlock=None)

        self.log.debugv("Published failed block notification for hash {} num {}"
                        .format(block_hash, block_num))

    # Can we put this on CatchupManager / BlockServer instead?
    def recv_new_block_notif(self, sender_vk: str, notif):
        self.log.debugv("MN got new block notification: {}".format(notif))

        blocknum = notif.blockNum

        if (blocknum > self.state.latest_block_num + 1) and \
           (notif.type.which() == "newBlock"):
            self.log.info("Block num {} on NBC does not match our block num {}! Triggering catchup".format(notif.block_num, self.state.latest_block_num))

            # Call intermediate sync on Block Fetcher
            self.block_fetcher.intermediate_sync(notif)
        else:
            self.log.debugv("Block num on NBC is LTE that ours. Ignoring")

    def recv_fail_block_notif(self, sender_vk: str, notif):
        self.log.debugv("MN got fail block notification: {}".format(notif))
        # TODO implement

    # Probably testable
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


