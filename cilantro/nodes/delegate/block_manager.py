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
from cilantro.storage.blocks import BlockStorageDriver
from cilantro.logger.base import get_logger
from cilantro.storage.db import VKBook
from cilantro.protocol.multiprocessing.worker import Worker
from cilantro.utils.lprocess import LProcess
from cilantro.utils.utils import int_to_bytes, bytes_to_int

from cilantro.constants.nodes import *
from cilantro.constants.zmq_filters import DEFAULT_FILTER
from cilantro.constants.ports import DELEGATE_ROUTER_PORT, DELEGATE_PUB_PORT, MASTER_PUB_PORT, MASTER_ROUTER_PORT 

from cilantro.messages.base.base import MessageBase
from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.consensus.block_contender import BlockContender
from cilantro.messages.block_data.block_metadata import NewBlockNotification
from cilantro.messages.consensus.sub_block_contender import SubBlockContender
from cilantro.messages.signals.make_next_block import MakeNextBlock

import asyncio
import zmq
import os
from collections import defaultdict

IPC_IP = 'block-manager-ipc-sock'
IPC_PORT = 6967

# convenience struct to maintain db snapshot state data in one place
class DBState:
    # def __init__(self, block_hash: int=0, timestamp: int=0):
    def __init__(self, block_hash: int=0):
        self.cur_block_hash = block_hash
        # self.cur_timestamp = timestamp   ?? probably not needed
        self.next_block = {}


class BlockManager(Worker):

    def __init__(self, ip, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = get_logger("BlockManager[{}]".format(self.verifying_key[:8]))

        self.ip = ip
        self.sb_builders = {}  # index -> process      # perhaps can be consolidated with the above ?
        self.tasks = []

        self.num_sub_blocks = len(VKBook.get_masternodes())  # same as num masternodes right now
        self.num_blocks = min(MAX_BLOCKS, self.num_sub_blocks)
        self.sub_blocks_per_block = (self.num_sub_blocks + self.num_blocks - 1) // self.num_blocks
        self.num_sb_builders = min(MAX_SUB_BLOCK_BUILDERS, self.sub_blocks_per_block)
        self.my_sb_index = self._get_my_index() % self.num_sb_builders

        # raghu todo tie to initial catch up logic as well as right place to do this
        # self.current_hash = BlockStorageDriver.get_latest_block_hash()
        current_hash = 0  # Falcon needs to add db interface modifications
        self.db_state = DBState(current_hash)
        self.master_quorum = 1  # TODO

        self.log.notice("\nBlockManager initializing with\nvk={vk}\nsubblock_index={sb_index}\n"
                        "num_sub_blocks={num_sb}\nnum_blocks={num_blocks}\nsub_blocks_per_block={sb_per_block}\n"
                        "num_sb_builders={num_sb_builders}\n"
                        .format(vk=self.verifying_key, sb_index=self.my_sb_index, num_sb=self.num_sub_blocks,
                                num_blocks=self.num_blocks, sb_per_block=self.sub_blocks_per_block,
                                num_sb_builders=self.num_sb_builders))
        assert self.num_sub_blocks >= self.num_blocks, "num_blocks cannot be more than num_sub_blocks"

        # Define Sockets (these get set in build_task_list)
        self.out_router, self.in_router, self.ipc_router, self.pub, self.sub = None, None, None, None, None
        self.ipc_ip = IPC_IP + '-' + str(os.getpid())

        self.run()
        self.log.critical("just called run!".format())

    def run(self):
        # DEBUG TODO DELETE
        self.log.critical("\n!!!! RUN CALLED !!!!!\n")
        # END DEBUG
        self.build_task_list()
        self.log.info("Block Manager starting...")
        self.start_sbb_procs()
        self.log.info("Catching up...")
        self.update_db_state()
        self.loop.run_until_complete(asyncio.gather(*self.tasks))

    def build_task_list(self):
        # davis ? do we need this many router sockets ??
        # can master nodes are the ones that bind their routers while delegates and witnesses connect only?
        # this works well if only all nodes connect to masters and masters don't need to connect to other masters??
        # Create ROUTER socket for bidirectional communication with masters over tcp
        self.in_router = self.manager.create_socket(socket_type=zmq.ROUTER, name="BM-IN-Router")
        self.in_router.bind(port=DELEGATE_ROUTER_PORT, protocol='tcp', ip=self.ip)
        self.tasks.append(self.in_router.add_handler(self.handle_in_router_msg))

        self.out_router = self.manager.create_socket(socket_type=zmq.ROUTER, name="BM-OUT-Router")
        self.tasks.append(self.out_router.add_handler(self.handle_out_router_msg))

        # Create ROUTER socket for bidirectional communication with SBBs over IPC
        self.ipc_router = self.manager.create_socket(socket_type=zmq.ROUTER, name="BM-IPC-Router")
        self.ipc_router.bind(port=IPC_PORT, protocol='ipc', ip=self.ipc_ip)
        self.tasks.append(self.ipc_router.add_handler(self.handle_ipc_msg))

        # Create PUB socket to publish new sub_block_contenders to all masters
        # Falcon - is it secure and has a different pub port ??
        #          do we have a corresponding sub at master that handles this properly ?
        self.pub = self.manager.create_socket(socket_type=zmq.PUB, name='SB Publisher')
        self.pub.bind(port=DELEGATE_PUB_PORT, protocol='tcp', ip=self.ip)

        # Create SUB socket to
        # 1) listen for subblock contenders from other delegates
        # 2) listen for NewBlockNotifications from masternodes
        self.sub = self.manager.create_socket(socket_type=zmq.SUB, name="BM-Sub")  # TODO secure him
        self.tasks.append(self.sub.add_handler(self.handle_sub_msg))

        # Listen to other delegates (NOTE: with no filter currently) - disable this for now
        # self.sub.setsockopt(zmq.SUBSCRIBE, b'')
        # for vk in VKBook.get_delegates():
            # if vk != self.verifying_key:  # Do not SUB to itself
                # self.sub.connect(vk=vk, port=INTER_DELEGATE_PORT)

        # Listen to Masternodes
        self.sub.setsockopt(zmq.SUBSCRIBE, DEFAULT_FILTER.encode())
        for vk in VKBook.get_masternodes():
            self.sub.connect(vk=vk, port=MASTER_PUB_PORT)
            self.out_router.connect(vk=vk, port=MASTER_ROUTER_PORT)

    def update_db_state(self):
        # do catch up logic here
        # only when one can connect to quorum masters and get db update, move to next step
        # at the end, it has updated its db state to consensus latest
        # latest_block_hash, list of mn vks
        envelope = BlockMetaDataRequest.create(current_block_hash=self.db_state.cur_block_hash)
        # send msg to each of the connected masters. Do we need to maintain a list of connected vks ??
        for vk in VKBook.get_masternodes():
            self.out_router.send_multipart([vk.encode(), envelope])
        # no need to wait for the replys as we have added a handler



    def start_sbb_procs(self):
        for i in range(self.num_sb_builders):
            self.sb_builders[i] = LProcess(target=SubBlockBuilder,
                                           kwargs={"ipc_ip": self.ipc_ip, "ipc_port": IPC_PORT,
                                                   "signing_key": self.signing_key, "ip": self.ip,
                                                   "sbb_index": i, "num_sb_builders": self.num_sb_builders,
                                                   "total_sub_blocks": self.num_sub_blocks,
                                                   "num_blocks": self.num_blocks})
            self.log.info("Starting SBB #{}".format(i))
            self.sb_builders[i].start()

    def _get_my_index(self):
        for index, vk in enumerate(VKBook.get_delegates()):
            if vk == self.verifying_key:
                return index

        raise Exception("Delegate VK {} not found in VKBook {}".format(self.verifying_key, VKBook.get_delegates()))


    def handle_in_router_msg(self, frames):     # ? is it frames or envelope
        pass


    def handle_out_router_msg(self, frames):     # ? is it frames or envelope
        envelope = Envelope.from_bytes(frames[-1])
        msg = envelope.message
        msg_hash = envelope.message_hash

        if isinstance(msg, BlockMetaDataRequest):
            self.handle_new_block(envelope)
        else:
            raise Exception("BlockManager got message type {} from SUB socket that it does not know how to handle"
                            .format(type(msg)))


    def handle_ipc_msg(self, frames):
        self.log.spam("Got msg over ROUTER IPC from a SBB with frames: {}".format(frames))  # TODO delete this
        assert len(frames) == 3, "Expected 3 frames: (id, msg_type, msg_blob). Got {} instead.".format(frames)

        sbb_index = bytes_to_int(frames[0])
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
        # This handle will get NewBlockNotifications from Masternodes, and whatever additional stuff??

        # The first frame is the filter, and the last frame is the envelope binary
        envelope = Envelope.from_bytes(frames[-1])
        msg = envelope.message
        msg_hash = envelope.message_hash

        if isinstance(msg, NewBlockNotification):
            self.handle_new_block(envelope)
        # not needed anymore ?? raghu TODO
        elif isinstance(msg, BlockContender):
            # TODO implement
            self.recv_sub_block(msg)
        else:
            raise Exception("BlockManager got message type {} from SUB socket that it does not know how to handle"
                            .format(type(msg)))
        # Last frame, frames[-1] will be the envelope binary

    def _handle_sbc(self, sbc: SubBlockContender):
        # TODO implement     raghu
        # publish to Masternode?
        # need to put it in an envelope and publish to master
        
        # envelope = BlockMetaDataRequest.create(current_block_hash=self.db_state.cur_block_hash)
        # frames = ''
        # self.pub.send_multipart(frames)
        pass

    def _send_msg_over_ipc(self, sb_index: int, message: MessageBase):
        """
        Convenience method to send a MessageBase instance over IPC router socket to a particular SBB process. Includes a
        frame to identify the type of message
        """
        assert isinstance(message, MessageBase), "Must pass in a MessageBase instance"
        id_frame = int_to_bytes(sb_index)
        message_type = MessageBase.registry[message]  # this is an int (enum) denoting the class of message
        self.ipc_router.send_multipart([id_frame, int_to_bytes(message_type), message.serialize()])

    # raghu todo - need to hook up catch logic with db_state
    # db state - initialize
    # ask for catch up
    # new blocks keep update
    def handle_new_block(self, envelope: Envelope):
        # raghu/davis - need to fix this data structure and handling it
        cur_block_hash = self.db_state.cur_block_hash
        # block_hash = get_block_hash(Envelope) # TODO
        block_hash = cur_block_hash + 1
        if (block_hash == self.cur_block_hash):
            # TODO log something
            return

        count = self.db_state.next_block.get(block_hash, 0) + 1
        if (count == self.master_quorum):      # TODO
            self.update_db(envelope.message)
            self.db_state.cur_block_hash = block_hash
            self.db_state.next_block.clear()
            self.send_updated_db_msg()
        else:
            self.next_block[block_hash] = num

    def send_updated_db_msg(self):
        message = MakeNextBlock.create()
        message_type = MessageBase.registry[message]
        msg = message.serialize()
        msg_type = int_to_bytes(message_type)
        for idx in range(self.num_sb_builders):
            id_frame = int_to_bytes(idx)
            self.ipc_router.send_multipart([id_frame, msg_type, msg])

