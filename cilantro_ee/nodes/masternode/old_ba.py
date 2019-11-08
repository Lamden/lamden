from cilantro_ee.core.logger.base import get_logger
from cilantro_ee.core.utils.worker import Worker

from cilantro_ee.services.storage.state import MetaDataStorage
from cilantro_ee.nodes.catchup import CatchupManager
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
import math, asyncio, zmq, time


from cilantro_ee.core.sockets.services import SocketStruct, SubscriptionService


class TransactionBatcherInformer:
    def __init__(self, socket_id):
        pass

    def send_ready(self):
        pass

    def send_burn_input_hashes(self):
        pass


class SubBlockBuilderSubscriber(SubscriptionService):
    pass


class BlockAggregator(Worker):

    def __init__(self, ip, ipc_ip, ipc_port, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = get_logger("BlockAggregator[{}]".format(self.verifying_key[:8]))

        assert self.verifying_key in PhoneBook.masternodes, "not a part of VKBook"

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

        self.my_mn_idx = PhoneBook.masternodes.index(self.verifying_key)
        self.my_sb_idx = self.my_mn_idx % NUM_SB_BUILDERS

        self.curr_block_hash = self.state.get_latest_block_hash()

        self.driver = CilantroStorageDriver(key=self.signing_key)

        last_block = self.driver.get_last_n(1, CilantroStorageDriver.INDEX)[0]
        latest_hash = last_block.get('blockHash')
        latest_num = last_block.get('blockNum')

        self.block_fetcher = BlockFetcher(wallet=self.wallet,
                                          ctx=self.zmq_ctx,
                                          blocks=self.driver,
                                          state=self.state)

        self.state.latest_block_num = latest_num
        self.state.latest_block_hash = latest_hash

        self.run()

    def run(self):
        self.log.info("Block Aggregator starting...")
        self.build_task_list()

        self.loop.run_until_complete(asyncio.gather(*self.tasks))

    def build_task_list(self):
        # Create ROUTER socket for communication with batcher over IPC
        # DEALER SOCKET...
        self.ipc_router = self.manager.create_socket(socket_type=zmq.ROUTER, name="BA-IPC-Router")
        self.ipc_router.bind(port=self.ipc_port, protocol='ipc', ip=self.ipc_ip)

        # SubscriptionService
        self.sub = self.manager.create_socket(
            socket_type=zmq.SUB,
            name="BA-Sub",
            secure=True,
        )
        self.sub.setsockopt(zmq.SUBSCRIBE, BLOCK_IDX_REQ_FILTER.encode())
        self.sub.setsockopt(zmq.SUBSCRIBE, DEFAULT_FILTER.encode())
        self.sub.setsockopt(zmq.SUBSCRIBE, NEW_BLK_NOTIF_FILTER.encode())

        # Regular Publish socket
        self.pub = self.manager.create_socket(
            socket_type=zmq.PUB,
            name="BA-Pub",
            secure=True,
        )
        self.pub.bind(ip=self.ip, port=MN_PUB_PORT)

        ### AsyncServer?
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
        # sync_genesis_contracts()
        # await self.block_fetcher.sync()

        await self._trigger_catchup()

    async def _trigger_catchup(self):
        self.log.info("Triggering catchup")
        # Add genesis contracts to state db if needed
        sync_genesis_contracts()

        self.catchup_manager.run_catchup()

### SUB MESSAGE LOOP SHOULD BE ASYNC
    def handle_sub_msg(self, frames):
        msg_filter, msg_type, msg_blob = frames
        self.log.success(len(frames))

        msg_type, msg, sender, timestamp, is_verified = Message.unpack_message(msg_type, msg_blob)
        if not is_verified:
            self.log.error("Failed to verify the message of type {} from {} at {}. Ignoring it .."
                          .format(msg_type, sender, timestamp))
            return

        # Move this socket to where the communication is happening (IE: the blockserver?)
        if msg_type == MessageType.BLOCK_INDEX_REQUEST:
            self.catchup_manager.recv_block_idx_req(msg)

        elif msg_type == MessageType.SUBBLOCK_CONTENDER:
            if not self.catchup_manager.is_catchup_done():
                self.log.info("Got SBC, but i'm still catching up. Ignoring: <{}>".format(msg))
            else:
                # todo needs to handle this ??
                # signature = subblock_capnp.MerkleProof.from_bytes_packed(msg.signature)
                self.recv_sub_block_contender(sender, msg)

        # Process block notification messages
        elif msg_type == MessageType.BLOCK_NOTIFICATION:
            self.log.important3(
                "BlockAGG got BlockNotification from sender {} with hash {}"
                .format(sender, msg.blockHash))
            # Process accordingly
            self.recv_new_block_notif(sender, msg)

    def _set_catchup_done(self):
        if not self._is_catchup_done:
            self._is_catchup_done = True
            self.curr_block_hash = self.state.get_latest_block_hash()
            self.curr_block.reset()

            mtype, msg = Message.get_message_packed(MessageType.READY)
            self.ipc_router.send_multipart([b'0', mtype, msg])

            time.sleep(3)

            # Construct a cryptographically signed message of the current time such that the receiver can verify it
            mtype, msg = Message.get_signed_message_packed(
                                    wallet=self.wallet,
                                    msg_type=MessageType.READY)

### Send signed READY signal on pub
            self.log.success('READY SIGNAL SENT TO SUBS')
            self.pub.send_msg(msg=msg, msg_type=mtype,
                              filter=DEFAULT_FILTER.encode())

    # Can we put this exclusively in Catchup manager?
    def handle_router_msg(self, frames):
        self.log.info('got message on block agg with frames {}'.format(frames))

        sender, msg_type, msg_blob = frames

        # need to distinguish between sender (remote socket identity vs. message signer which is vk)
        msg_type, msg, signee, timestamp, is_verified = Message.unpack_message(msg_type, msg_blob)
        if not is_verified:
            self.log.error("Failed to verify the message of type {} from {} at {}. Ignoring it .."
                          .format(msg_type, sender, timestamp))
            return

        # When does this happen?
        if msg_type == MessageType.BLOCK_INDEX_REPLY:
            if self.catchup_manager.recv_block_idx_reply(sender, msg):
                self._set_catchup_done()

        elif msg_type == MessageType.BLOCK_DATA_REQUEST:
            self.catchup_manager.recv_block_data_req(sender, msg)

        elif msg_type == MessageType.BLOCK_DATA:
            if self.catchup_manager.recv_block_data_reply(msg):
                self._set_catchup_done()


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
            self.catchup_manager.recv_new_blk_notif(notif)
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
