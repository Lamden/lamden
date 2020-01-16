import time
import asyncio
from cilantro_ee.core.logger import get_logger
from cilantro_ee.constants.zmq_filters import *
from cilantro_ee.core.sockets.lsocket import LSocketBase
from cilantro_ee.services.storage.vkbook import VKBook
from cilantro_ee.services.storage.state import MetaDataStorage
from cilantro_ee.services.storage.master import CilantroStorageDriver
from cilantro_ee.services.storage.master import MasterStorage
from cilantro_ee.contracts.sync import sync_genesis_contracts

from cilantro_ee.core.messages.message_type import MessageType
from cilantro_ee.core.messages.message import Message

from cilantro_ee.core.nonces import NonceManager

IDX_REPLY_TIMEOUT = 20
TIMEOUT_CHECK_INTERVAL = 1


class CatchupManager:
    def __init__(self, verifying_key: str, signing_key: str, pub_socket, router_socket: LSocketBase, store_full_blocks=True):
        """

        :param verifying_key: host vk
        :param pub_socket:
        :param router_socket:
        :param store_full_blocks: Master node uses this flag to indicate block storage
        """
        self.log = get_logger("CatchupManager")

        self.vkbook = VKBook()

        # infra input
        self.pub, self.router = pub_socket, router_socket
        self.verifying_key = verifying_key
        self.signing_key = signing_key
        self.store_full_blocks = store_full_blocks

        # self.blocks = CilantroStorageDriver(key=self.signing_key)

        self.state = MetaDataStorage()
        self.nonce_manager = NonceManager()

        # catchup state
        self.is_caught_up = False
        self.timeout_catchup = time.time()      # 10 sec time we will wait for 2/3rd MN to respond
        self.node_idx_reply_set = set()  # num of master responded to catch up req

        # main list to process
        self.block_delta_list = []       # list of mn_index dict to process

        # received full block could be out of order
        self.rcv_block_dict = {}                 # DS stores any Out of order received blocks

        # loop to schedule timeouts
        self.timeout_fut = None

        self.my_quorum = self.vkbook.masternode_quorum_min

        # masternode should make sure redis and mongo are in sync
        if store_full_blocks:
            self.my_quorum -= 1
            self.update_state()

        self.curr_hash = self.state.latest_block_hash
        self.curr_num = self.state.latest_block_num

        self.target_blk_num = self.curr_num
        self.awaited_blknum = self.curr_num

        # DEBUG -- TODO DELETE
        self.log.test("CatchupManager VKBook MN's: {}".format(self.vkbook.masternodes))
        self.log.test("CatchupManager VKBook Delegates's: {}".format(self.vkbook.delegates))
        # END DEBUG

        self.nonce_manager = NonceManager(driver=self.state)

        if self.store_full_blocks:
            self.driver = CilantroStorageDriver(key=self.signing_key)
        else:
            self.driver = None

    def update_state(self):
        """
        Sync block and state DB if either is out of sync.
        :return:
        """
        self.driver = CilantroStorageDriver(key=self.signing_key)

        last_block = self.driver.get_last_n(1, MasterStorage.INDEX)[0]

        db_latest_blk_num = last_block.get('blockNum')

        latest_state_num = self.state.latest_block_num
        if db_latest_blk_num < latest_state_num:
            # TODO - assert and quit
            self.log.fatal("Block DB block - {} is behind StateDriver block - {}. Cannot handle"
                           .format(db_latest_blk_num, latest_state_num))
            # we need to rebuild state from scratch
            latest_state_num = 0
            self._reset_state()

        if db_latest_blk_num > latest_state_num:
            self.log.info("StateDriver block num {} is behind DB block num {}".format(latest_state_num, db_latest_blk_num))
            while latest_state_num < db_latest_blk_num:
                latest_state_num = latest_state_num + 1
                # TODO get nth full block wont work for now in distributed storage
                blk_dict = self.driver.get_block(latest_state_num)

                if '_id' in blk_dict:
                    del blk_dict['_id']

                block = Message.get_message(MessageType.BLOCK_DATA, **blk_dict)
                self.state.update_with_block(block=block)

        # Reinitialize the latest nonce. This should probably be abstracted into a seperate class at a later date
        blk_dict = self.driver.get_block(latest_state_num)
        sbs = blk_dict.get('subBlocks')

        nonces = {}

        # raghu todo - need to revisit this? why do we serialize sub-blocks only, but not block
        if sbs is not None:
            for raw_sb in blk_dict['subBlocks']:
                subblock = Message.unpack_message_internal(MessageType.SUBBLOCK, raw_sb)
                self.log.info('Block: {}'.format(subblock))
                for tx in subblock.transactions:
                    self.nonce_manager.update_nonce_hash(nonce_hash=nonces, tx_payload=tx.transaction.payload)
                    self.state.set_transaction_data(tx=tx)

        self.nonce_manager.commit_nonces(nonce_hash=nonces)
        self.nonce_manager.delete_pending_nonces()

        self.log.info("Verify StateDriver num {} StorageDriver num {}".format(latest_state_num, db_latest_blk_num))

    # should be called only once per node after bootup is done
    def run_catchup(self, ignore=False):
        self.log.info("-----RUN CATCHUP-----")
        # check if catch up is already running
        if ignore and self.is_catchup_done():
            self.log.warning("Already caught up. Ignoring to run it again.")
            return

        if self.my_quorum == 0:    # only one master available
            self.is_caught_up = True
            return

        # first reset state variables
        self.node_idx_reply_set.clear()
        self.is_caught_up = False
        # self.curr_hash, self.curr_num = StateDriver.get_latest_block_info()
        # self.target_blk_num = self.curr_num
        # self.awaited_blknum = None

        # starting phase I
        self.timeout_catchup = time.time()
        self.send_block_idx_req()

        self._reset_timeout_fut()
        # first time wait longer than usual
        time.sleep(3 * TIMEOUT_CHECK_INTERVAL)
        self.timeout_fut = asyncio.ensure_future(self._check_timeout())
        self.log.important2("Running catchup!")

    def _reset_state(self):
        # only in a very rare case where mongo db is behind redis, this is called
        self.state.flush()
        sync_genesis_contracts()

    def _reset_timeout_fut(self):
        if self.timeout_fut:
            if not self.timeout_fut.done():
                # TODO not sure i need this try/execpt here --davis
                try: self.timeout_fut.cancel()
                except: pass
            self.timeout_fut = None

    async def _check_timeout(self):
        async def _timeout():
            elapsed = 0
            while elapsed < IDX_REPLY_TIMEOUT:
                elapsed += TIMEOUT_CHECK_INTERVAL
                await asyncio.sleep(TIMEOUT_CHECK_INTERVAL)

                if self._check_idx_reply_quorum() is True:
                    self.log.debugv("Quorum reached!")
                    return

            # If we have not returned from the loop and the this task has not been canceled, initiate a retry
            self.log.warning("Timeout of {} reached waiting for block idx replies! Resending BlockIndexRequest".format(IDX_REPLY_TIMEOUT))
            self.timeout_fut = None
            self.run_catchup(ignore=True)

        try:
            await _timeout()
        except asyncio.CancelledError as e:
            pass

    # Phase I start
    def send_block_idx_req(self):
        """
        Multi-casting BlockIndexRequests to all master nodes with current block hash
        :return:
        """
        self.log.info("Multi cast BlockIndexRequests to all MN with current block hash {}".format(self.curr_hash))

        msg_type, msg = Message.get_message_packed(
                                      MessageType.BLOCK_INDEX_REQUEST,
                                      blockHash=self.curr_hash,
                                      sender=self.verifying_key)

        self.pub.send_msg(BLOCK_IDX_REQ_FILTER.encode(), msg_type, msg)

    def _recv_block_idx_reply(self, sender_vk: str, reply):
        self.log.info('Got REPLY from {} as {}'.format(sender_vk, reply))
        """
        We expect to receive this message from all mn/dn
        :param sender_vk:
        :param reply:
        :return:
        """
        if sender_vk in self.node_idx_reply_set:
            return      # already processed

        if reply == b'':
            self.node_idx_reply_set.add(sender_vk)
            self.log.important("Received BlockIndexReply with no index info from masternode {}".format(sender_vk))
            return

        tmp_list = reply.get('indices')
        if len(tmp_list) > 1:
            assert tmp_list[0].get('blockNum') > tmp_list[-1].get('blockNum'), "ensure reply are in ascending order {}"\
                .format(tmp_list)
            tmp_list.reverse()

        self.log.debugv("tmp list -> {}".format(tmp_list))
        self.new_target_blk_num = tmp_list[-1].get('blockNum') if len(tmp_list) > 0 else 0
        new_blks = self.new_target_blk_num - self.target_blk_num

        if new_blks > 0:
            self.target_blk_num = self.new_target_blk_num
            update_list = tmp_list[-new_blks:]
            self.block_delta_list.extend(update_list)
            if self.awaited_blknum == self.curr_num:
                self.process_recv_idx()

        self.node_idx_reply_set.add(sender_vk)
        self.log.debugv("_new target block num {}\ntarget block num {}\ntemp list {}"
                        .format(self.new_target_blk_num, self.target_blk_num, tmp_list))

    def recv_block_idx_reply(self, sender_vk: str, reply):
        self._recv_block_idx_reply(sender_vk, reply.to_dict())
        # self.log.important2("RCV BIRp")
        return self.is_catchup_done()

    def _send_block_data_req(self, mn_vk, req_blk_num):
        self.log.info("Unicast BlockDateRequests to masternode owner with current block num {} key {}"
                      .format(req_blk_num, mn_vk))
        msg_type, msg = Message.get_message_packed(
                                      MessageType.BLOCK_DATA_REQUEST,
                                      blockNum=req_blk_num)
        self.router.send_msg(mn_vk, msg_type, msg)

    def _recv_block_data_reply(self, reply):
        # check if given block is older thn expected drop this reply
        # check if given blocknum grter thn current expected blk -> store temp
        # if given block needs to be stored update state/storage delete frm expected DT
        self.log.info('Recieved {}:'.format(reply))

        rcv_blk_num = reply.blockNum
        if rcv_blk_num <= self.curr_num:
            self.log.debug2("dropping already processed blk reply blk-{}:hash-{} ".format(reply.blockNum, reply.blockHash))
            return

        self.rcv_block_dict[rcv_blk_num] = reply
        # WHY IS AWAITED BLK NUM NONE HERE ???
        if rcv_blk_num > self.awaited_blknum:
            self.log.debug2("Got block num {}, still awaiting block num {}".format(rcv_blk_num, self.awaited_blknum))
            return

        if (rcv_blk_num == self.awaited_blknum):
            self.log.info('Got the block I needed!')
            self.curr_num = self.awaited_blknum
            self.update_received_block(block = reply)
            self.process_recv_idx()

    def recv_block_data_reply(self, block):
        self._recv_block_data_reply(block)
        return self.is_catchup_done()

    # MASTER ONLY CALL
    def recv_block_idx_req(self, request):
        """
        Receive BlockIndexRequests calls storage blocks to process req and build response
        :param requester_vk:
        :param request:
        :return:
        """
        requester_vk = request.sender

        assert self.store_full_blocks, "Must be able to store full blocks to reply to state update requests"
        self.log.debugv("Got block index request from sender {} requesting block hash {} my_vk {}"
                        .format(requester_vk, request.blockHash, self.verifying_key))

        if requester_vk == self.verifying_key:
            self.log.debugv("received request from myself dropping the req")
            return

        if self.is_caught_up:
            self.curr_hash = self.state.latest_block_hash
            self.curr_num = self.state.latest_block_num

        # tejas, latest_blk_num should correspond to request.block_hash or latest_num ?
        delta_idx = self.get_idx_list(vk=requester_vk,
                                      latest_blk_num=self.curr_num,
                                      sender_bhash=request.blockHash)

        if delta_idx is None:
            delta_idx = []

        self.log.debugv("Delta list {} for blk_num {} blk_hash {}".format(delta_idx, self.curr_num,
                                                                          request.blockHash))

        if delta_idx and len(delta_idx) > 1:
            assert delta_idx[0].get('blockNum') > delta_idx[-1].get('blockNum'), "ensure reply are in ascending order" \
                                                                                  " {}" .format(delta_idx)

        self._send_block_idx_reply(reply_to_vk=requester_vk,
                                   catchup_list=delta_idx)

    def _recv_blk_notif(self, update):
        # can get any time - hopefully one incremental request, how do you handle it in all cases?
        nw_blk_num = update.blockNum
        if self.is_caught_up: # is caught up is current height - block notif height = -1
            self.curr_hash = self.state.latest_block_hash
            self.curr_num = self.state.latest_block_num
            self.target_blk_num = self.curr_num
            self.awaited_blknum = self.curr_num
        if (nw_blk_num <= self.curr_num) or (nw_blk_num <= self.target_blk_num):
            return
        if nw_blk_num > (self.target_blk_num + 1):
            self.run_catchup()
        else:
            # actually you can request block data directly
            for vk in update.blockOwners:
                self.node_idx_reply_set.add(vk)
            self.is_caught_up = False
            self.target_blk_num = nw_blk_num
            if self.awaited_blknum == self.curr_num:
                self.awaited_blknum += 1
            for vk in update.blockOwners:
                self._send_block_data_req(mn_vk = vk, req_blk_num = nw_blk_num)

    def recv_new_blk_notif(self, update):
        self._recv_blk_notif(update)
        return self.is_catchup_done()

    # todo handle mismatch between redis and monodb
    # MASTER ONLY CALL
    def _send_block_idx_reply(self, reply_to_vk, catchup_list=[]):
        # this func doesnt care abt catchup_state we respond irrespective
        self.log.info("catchup list -> {}".format(catchup_list))

        msg_type, msg = Message.get_message_packed(
                                      MessageType.BLOCK_INDEX_REPLY,
                                      indices=catchup_list)

        self.log.debugv("Sending block index reply to vk {}, catchup {}".format(reply_to_vk, catchup_list))
        self.router.send_msg(filter=reply_to_vk,
                             msg_type=msg_type,
                             msg=msg)

    def get_idx_list(self, vk, latest_blk_num, sender_bhash):
        # check if requester is master or del
        self.log.info(sender_bhash)
        core_nodes = self.vkbook.masternodes + self.vkbook.delegates
        valid_node = vk.decode() in core_nodes

        if valid_node:

            index = self.driver.get_index(sender_bhash)

            given_blk_num = index.get('blockNum') if index else 0

            self.log.debugv('given block is already latest hash - {} givenblk - {} curr-{}'
                            .format(sender_bhash, given_blk_num, latest_blk_num))

            if given_blk_num == latest_blk_num:
                self.log.debug('given block is already latest')
                return None
            else:
                idx_delta = self.driver.get_last_n(latest_blk_num - given_blk_num)
                return idx_delta

        assert valid_node, "invalid vk given key is not of master/delegate/statestync dumping vk {}".format(vk)

    # removed flooding, but it could be too sequential?
    # use futures to control rate of requests?
    def process_recv_idx(self):
        if (self.awaited_blknum <= self.curr_num) and (self.awaited_blknum < self.target_blk_num):
            self.awaited_blknum = self.curr_num + 1
            # don't request if it is in stashed list. move to next one
            while self.awaited_blknum in self.rcv_block_dict:
                self.awaited_blknum = self.awaited_blknum + 1
            blknum = 0
            blk_ptr = None
            while (blknum < self.awaited_blknum) and len(self.block_delta_list):
                blk_ptr = self.block_delta_list.pop(0)
                blknum = blk_ptr.get('blockNum')

            if blknum < self.awaited_blknum:
                return

            mn_list = blk_ptr.get('blockOwners')
            for vk in mn_list:
                self._send_block_data_req(mn_vk = vk, req_blk_num = self.awaited_blknum)

    def update_received_block(self, block=None):
        assert self.curr_num in self.rcv_block_dict, "not found the received block!"
        cur_num = self.curr_num
        while cur_num in self.rcv_block_dict:
            block = self.rcv_block_dict[cur_num]
            if self.store_full_blocks is True:
                update_blk_result = bool(self.driver.evaluate_wr(entry=block._data.to_dict()))
                assert update_blk_result is True, "failed to update block"

            self.state.update_with_block(block)
            self.curr_num = cur_num
            cur_num = cur_num + 1

        self.curr_hash = self.state.latest_block_hash
        self.curr_num = self.state.latest_block_num

    def _check_idx_reply_quorum(self):
        return len(self.node_idx_reply_set) >= self.my_quorum

    def is_catchup_done(self):
        if self.is_caught_up:
            return True
        self.is_caught_up = (self.target_blk_num == self.curr_num) and \
                            self._check_idx_reply_quorum()

        return self.is_caught_up


