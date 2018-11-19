"""
    BlockManager  (main process of delegate)

    This is the main workhorse for managing inter node communication as well as
    coordinating the interpreting and creation of sub-block contenders that form part of new block.
    It creates sub-block builder processes to manage the parallel execution of different sub-blocks.
    It will also participate in conflict resolution of sub-blocks
    It publishes those sub-blocks to masters so they can assemble the new block contender

    It manages the new block notifications from master and update the db snapshot state
    so sub-block builders can proceed to next block

"""

from cilantro.nodes.delegate.sub_block_builder import SubBlockBuilder
from cilantro.storage.driver import StorageDriver
from cilantro.logger.base import get_logger
from cilantro.storage.db import VKBook
from cilantro.protocol.multiprocessing.worker import Worker
from cilantro.utils.lprocess import LProcess
from cilantro.utils.hasher import Hasher
from cilantro.utils.utils import int_to_bytes, bytes_to_int
# from cilantro.protocol.interpreter import SenecaInterpreter
from cilantro.messages.block_data.block_data import BlockData
from typing import List

from cilantro.constants.system_config import *
from cilantro.constants.zmq_filters import DEFAULT_FILTER
from cilantro.constants.ports import *

from cilantro.messages.base.base import MessageBase
from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.block_data.block_metadata import NewBlockNotification
from cilantro.messages.consensus.sub_block_contender import SubBlockContender
from cilantro.messages.signals.delegate import MakeNextBlock, DiscardPrevBlock
from cilantro.messages.block_data.state_update import StateUpdateReply, StateUpdateRequest

import asyncio
import zmq
import os
import time
import random
from collections import defaultdict

IPC_IP = 'block-manager-ipc-sock'
IPC_PORT = 6967

# convenience struct to maintain db snapshot state data in one place
class DBState:
    def __init__(self, cur_block_hash):
        self.cur_block_hash = cur_block_hash
        self.next_block_hash = cur_block_hash
        self.next_block = {}
        self.sub_block_hash_map = {}
        # self.cur_timestamp = timestamp   ?? probably not needed


class BlockManager(Worker):

    def __init__(self, ip, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = get_logger("BlockManager[{}]".format(self.verifying_key[:8]))
        self.tasks = []

        self.ip = ip
        self.sb_builders = {}  # index -> process
        self.sb_index = self._get_my_index() % NUM_SB_BUILDERS

        # raghu todo tie to initial catch up logic as well as right place to do this
        # Falcon needs to add db interface modifications
        # self.db_state = DBState(BlockStorageDriver.get_latest_block_hash())
        self.db_state = DBState(StorageDriver.get_latest_block_hash())
        # self.interpreter = SenecaInterpreter()

        self.log.notice("\nBlockManager initializing with\nvk={vk}\nsubblock_index={sb_index}\n"
                        "num_sub_blocks={num_sb}\nnum_blocks={num_blocks}\nsub_blocks_per_block={sb_per_block}\n"
                        "num_sb_builders={num_sb_builders}\n"
                        .format(vk=self.verifying_key, sb_index=self.sb_index, num_sb=NUM_SUB_BLOCKS,
                                num_blocks=NUM_BLOCKS, sb_per_block=NUM_SB_PER_BLOCK,
                                num_sb_builders=NUM_SB_BUILDERS))

        # Define Sockets (these get set in build_task_list)
        self.router, self.ipc_router, self.pub, self.sub = None, None, None, None
        self.ipc_ip = IPC_IP + '-' + str(os.getpid()) + '-' + str(random.randint(0, 2**32))

        self.run()

    def run(self):
        self.build_task_list()
        self.log.info("Block Manager starting...")
        self.start_sbb_procs()
        self.log.info("Catching up...")
        self.catchup_db_state()

        # here we fix call to send_updated_db_msg until we properly send back StateUpdateReply from Masternodes
        # TODO -- remove once Masternodes can reply to StateUpdateRequest
        self.send_updated_db_msg()

        # DEBUG -- TODO DELETE
        # self.tasks.append(self.spam_sbbs())
        # END DEBUG

        self.loop.run_until_complete(asyncio.gather(*self.tasks))

    async def spam_sbbs(self):
        while True:
            await asyncio.sleep(4)
            for i in self.sb_builders:
                id_frame = str(i).encode()
                self.log.spam("sending test ipc msg to sb_builder id {}".format(id_frame))
                self.ipc_router.send_multipart([id_frame, int_to_bytes(1), b'hi its me the block manager'])

    def build_task_list(self):
        # Create a TCP Router socket for comm with other nodes
        self.router = self.manager.create_socket(socket_type=zmq.ROUTER, name="BM-Router", secure=True)
        self.router.setsockopt(zmq.IDENTITY, self.verifying_key.encode())
        self.router.setsockopt(zmq.ROUTER_MANDATORY, 1)  # FOR DEBUG ONLY
        self.router.bind(port=DELEGATE_ROUTER_PORT, protocol='tcp', ip=self.ip)
        self.tasks.append(self.router.add_handler(self.handle_router_msg))

        # Create ROUTER socket for bidirectional communication with SBBs over IPC
        self.ipc_router = self.manager.create_socket(socket_type=zmq.ROUTER, name="BM-IPC-Router")
        self.ipc_router.setsockopt(zmq.ROUTER_MANDATORY, 1)  # FOR DEBUG ONLY
        self.ipc_router.bind(port=IPC_PORT, protocol='ipc', ip=self.ipc_ip)
        self.tasks.append(self.ipc_router.add_handler(self.handle_ipc_msg))

        # Create PUB socket to publish new sub_block_contenders to all masters
        # Falcon - is it secure and has a different pub port ??
        #          do we have a corresponding sub at master that handles this properly ?
        self.pub = self.manager.create_socket(socket_type=zmq.PUB, name='SB Publisher', secure=True)
        self.pub.bind(port=DELEGATE_PUB_PORT, protocol='tcp', ip=self.ip)

        # Create SUB socket to
        # 1) listen for subblock contenders from other delegates
        # 2) listen for NewBlockNotifications from masternodes
        self.sub = self.manager.create_socket(socket_type=zmq.SUB, name="BM-Sub", secure=True)
        self.tasks.append(self.sub.add_handler(self.handle_sub_msg))

        # Listen to Masternodes
        self.sub.setsockopt(zmq.SUBSCRIBE, DEFAULT_FILTER.encode())
        for vk in VKBook.get_masternodes():
            self.sub.connect(vk=vk, port=MASTER_PUB_PORT)
            time.sleep(1)
            self.router.connect(vk=vk, port=MASTER_ROUTER_PORT)
            time.sleep(1)

    def catchup_db_state(self):
        # do catch up logic here
        # only when one can connect to quorum masters and get db update, move to next step
        # at the end, it has updated its db state to consensus latest
        # latest_block_hash, list of mn vks
        # send msg to each of the connected masters. Do we need to maintain a list of connected vks ??
        # TODO send this over PUB to all masternodes instead of Router

        # TODO add this code when we can ensure block manager's router is properly set up...

        # envelope = StateUpdateRequest.create(block_hash=self.db_state.cur_block_hash)
        # for vk in VKBook.get_masternodes():
        #     self.router.send_msg(envelope, header=vk.encode())

        # no need to wait for the replys as we have added a handler
        pass

    def start_sbb_procs(self):
        for i in range(NUM_SB_BUILDERS):
            self.sb_builders[i] = LProcess(target=SubBlockBuilder, name="SBB_Proc-{}".format(i),
                                           kwargs={"ipc_ip": self.ipc_ip, "ipc_port": IPC_PORT,
                                                   "signing_key": self.signing_key, "ip": self.ip,
                                                   "sbb_index": i})
            self.log.info("Starting SBB #{}".format(i))
            self.sb_builders[i].start()

        # Sleep to SBB's IPC sockets are ready for any messages from BlockManager
        time.sleep(4)
        self.log.debugv("Done sleeping sleeping after starting SBB procs")

    def _get_my_index(self):
        for index, vk in enumerate(VKBook.get_delegates()):
            if vk == self.verifying_key:
                return index

        raise Exception("Delegate VK {} not found in VKBook {}".format(self.verifying_key, VKBook.get_delegates()))

    def handle_ipc_msg(self, frames):
        # DEBUG -- TODO DELETE
        # self.log.important2("Got msg over ROUTER IPC from a SBB with frames: {}".format(frames))  # TODO delete this
        # return
        # END DEBUG
        self.log.spam("Got msg over ROUTER IPC from a SBB with frames: {}".format(frames))  # TODO delete this
        assert len(frames) == 3, "Expected 3 frames: (id, msg_type, msg_blob). Got {} instead.".format(frames)

        sbb_index = int(frames[0].decode())
        assert sbb_index in self.sb_builders, "Got IPC message with ID {} that is not in sb_builders {}" \
            .format(sbb_index, self.sb_builders)

        msg_type = bytes_to_int(frames[1])
        msg_blob = frames[2]
        msg = MessageBase.registry[msg_type].from_bytes(msg_blob)
        self.log.debugv("BlockManager received an IPC message from sbb_index {} with message {}".format(sbb_index, msg))

        if isinstance(msg, SubBlockContender):
            self._handle_sbc(msg)
        # elif isinstance(msg, SomeOtherType):
        #     self._handle_some_other_type_of_msg(msg)
        else:
            raise Exception("BlockManager got unexpected Message type {} over IPC that it does not know how to handle!"
                            .format(type(msg)))

    def handle_sub_msg(self, frames):
        # TODO filter out duplicate NewBlockNotifications
        # (masters should not be sending more than 1, but we should be sure)

        envelope = Envelope.from_bytes(frames[-1])
        msg = envelope.message
        msg_hash = envelope.message_hash

        if isinstance(msg, NewBlockNotification):
            self.log.important3("BM got NewBlockNotification from sender {} with hash {}".format(envelope.sender, msg.block_hash))
            self.handle_new_block(msg)
        else:
            raise Exception("BlockManager got message type {} from SUB socket that it does not know how to handle"
                            .format(type(msg)))
        # Last frame, frames[-1] will be the envelope binary

    def handle_router_msg(self, frames):
        # self.log.important("Got msg over tcp ROUTER socket with frames: {}".format(frames))
        # TODO implement
        # TODO verify that the first frame (identity frame) matches the verifying key on the Envelope's seal

        envelope = Envelope.from_bytes(frames[-1])
        msg = envelope.message
        msg_hash = envelope.message_hash

        if isinstance(msg, StateUpdateReply):
            self.handle_state_update_reply(msg)
        else:
            raise Exception("BlockManager got message type {} from SUB socket that it does not know how to handle"
                            .format(type(msg)))

    def update_db_state(self, block_data: BlockData):
        txs_list = block_data.transactions
        # for txn in txs_list:
        #     self.interpreter.interpret(txn)
        # self.interpreter.flush()      # save and reset
        self.db_state.cur_block_hash = block_data.block_hash
        self.log.important("Caught up to block with hash {}".format(self.db_state.cur_block_hash))

    def handle_state_update_reply(self, msg: StateUpdateReply):
        # TODO need to handle the duplicates from a single sender (intentional attack?)
        # sender = envelope.sender
        # TODO also need to worry about quorum, etc
        # bd_map = {}
        bd_list = msg.block_data
        for block_data in bd_list:
            prev_block_hash = block_data.prev_block_hash
            if self.db_state.cur_block_hash == prev_block_hash:
                self.update_db_state(block_data)
            else:
                # bd_map[prev_block_hash] = block_data
                # ignore right now - just log
                self.log.important("Ignore block data with prev block hash {}".format(prev_block_hash))

    def _handle_sbc(self, sbc: SubBlockContender):
        self.db_state.sub_block_hash_map[sbc.result_hash] = sbc.sb_index
        self.log.important("Got SBC with sb-index {}. Sending to Masternodes.".format(sbc.sb_index))
        self.pub.send_msg(sbc, header=DEFAULT_FILTER.encode())
        if self.db_state.next_block_hash != self.db_state.cur_block_hash:
            num_sb = len(self.db_state.sub_block_hash_map)
            if num_sb == NUM_SB_PER_BLOCK:  # got all sub_block
                self.update_db()

    def _send_msg_over_ipc(self, sb_index: int, message: MessageBase):
        """
        Convenience method to send a MessageBase instance over IPC router socket to a particular SBB process. Includes a
        frame to identify the type of message
        """
        self.log.spam("Sending msg to sb_index {} with payload {}".format(sb_index, message))
        assert isinstance(message, MessageBase), "Must pass in a MessageBase instance"
        id_frame = str(sb_index).encode()
        message_type = MessageBase.registry[type(message)]  # this is an int (enum) denoting the class of message
        self.ipc_router.send_multipart([id_frame, int_to_bytes(message_type), message.serialize()])

    def update_db(self):
        # first sort the sb result hashes based on sub block index
        sorted_sb_hashes = sorted(self.db_state.sub_block_hash_map.keys(),
                                  key=lambda result_hash: self.db_state.sub_block_hash_map[result_hash])
        # append prev block hash
        our_block_hash = BlockData.compute_block_hash(sbc_roots=sorted_sb_hashes, prev_block_hash=self.db_state.cur_block_hash)
        if (our_block_hash == self.db_state.next_block_hash):
            # we have consensus
            self.log.success2("BlockManager achieved consensus on NewBlockNotification!")
            self.send_updated_db_msg()
            self.db_state.cur_block_hash = our_block_hash
            self.db_state.sub_block_hash_map.clear()
            self.db_state.next_block.clear()
        else:
            # we can't handle this with current Seneca. TODO
            self.log.fatal("Error: mismatch between current db state with masters!! my est bh {} and masters bh {}".format(our_block_hash, self.db_state.next_block_hash))

    def update_db_if_ready(self, block_data: NewBlockNotification):
        self.db_state.next_block_hash = block_data.block_hash
        # check if we have all sub_blocks
        num_sb = len(self.db_state.sub_block_hash_map)
        if (num_sb < NUM_SB_PER_BLOCK):  # don't have all sub-blocks
            self.log.info("I don't have all SBs")
            # since we don't have a way to sync Seneca with full data from master, just wait for sub-blocks done
            return
        self.update_db()

    # update current db state to the new block
    def handle_new_block(self, block_data: NewBlockNotification):
        new_block_hash = block_data.block_hash
        self.log.info("Got new block notification with block hash {}...".format(new_block_hash))

        if new_block_hash == self.db_state.cur_block_hash:
            self.log.info("New block notification is same as current state. Ignoring.")
            return

        count = self.db_state.next_block.get(new_block_hash, 0) + 1
        if count >= MIN_NEW_BLOCK_MN_QOURUM:
            self.log.info("New block quorum met!")
            self.update_db_if_ready(block_data)
        else:
            self.db_state.next_block[new_block_hash] = count

    def send_updated_db_msg(self):
        self.log.info("Sending MakeNextBlock message to SBBs")
        message = MakeNextBlock.create()
        for idx in range(NUM_SB_BUILDERS):
            self._send_msg_over_ipc(sb_index=idx, message=message)
