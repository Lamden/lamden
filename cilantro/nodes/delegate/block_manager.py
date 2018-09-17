"""
    BlockManager  (main process of delegate)

    This should coordinate the resolution mechanism for inter-subblock conflicts.
    It will also stitch two subblocks into one subtree and send to master and other delegates for voting.
    And will send in its vote on other subtrees to master directly when received from other delegates

    It can also have a thin layer of row conflict info that can be used to push some transactions to next block if they are conflicting with transactions in flight
    It will rotate asking 16 sets of sub-block-builders to proceed.

    It will also get new block notifications from master and can update its thin layer caching
        ask next set of sub-block-builders to proceed
        communicate failed contracts to previous sub-block-builder (SBB) either to reject or repeat in next block
    manages a pool of 64 processes for SBB.
    also spawns a thread for overlay network

    Input:
      - responsible subtree (based on delegate ordering ??? constant until next election)

    need to decide whether this code will live in delegate.py under Delegate class or 
    Delegate class will contain this class as a data structure and manage this and other stuff
    
    1. open my pub sockets: 1 -> publishes sub-blocks (master_delegate_filter), votes (master filter)
    2. create my sub sockets: 2 -> 1. master (gets new block) 2. delegates (gets sub-blocks - master_delegate_filter) initiates votes
    3. sub-block builder processes and socket pairs -> gets new sub-blocks made
    4. router / dealer sockets ?? 
    5. bind sub sockets to proper pubs
       main:
       subs:   masters
                 new block notification
               other delegates
       sbb:
       subs:  witnesses
"""

from cilantro.nodes.delegate.sub_block_builder import SubBlockBuilder
from cilantro.storage.blocks import BlockStorageDriver
from cilantro.logger.base import get_logger
from cilantro.storage.db import VKBook
from cilantro.protocol.multiprocessing.worker import Worker
from cilantro.utils.lprocess import LProcess

from cilantro.constants.nodes import *
from cilantro.constants.zmq_filters import MASTERNODE_DELEGATE_FILTER
from cilantro.constants.ports import INTER_DELEGATE_PORT, MN_NEW_BLOCK_PUB_PORT
from cilantro.constants.testnet import WITNESS_MN_MAP, MN_WITNESS_MAP

from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.consensus.block_contender import BlockContender
from cilantro.messages.block_data.block_metadata import NewBlockNotification

import asyncio
import zmq
import os
from collections import defaultdict

# communication
# From master:
#   Drop witness(es) - list
#   Add witness(es) - list
#   New Block Notification
# From Delegate (BM)
#   Request Witness list
#   Request latest block hash  (can be combined with req witness list)
#   Request block data since hash
#   send sub-tree(i) with sig + data
#   Send sig for sub-tree(i)
#   send Ready ??

IPC_IP = 'block-manager-ipc-sock'
IPC_PORT = 6967


class BlockManager(Worker):

    def __init__(self, ip, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = get_logger("BlockManager[{}]".format(self.verifying_key[:8]))

        self.ip = ip
        self.current_hash = BlockStorageDriver.get_latest_block_hash()
        self.mn_indices = self._build_mn_indices()
        self.sb_builders = {}  # index -> process      # perhaps can be consolidated with the above ?
        self.tasks = []

        self.num_mnodes = len(VKBook.get_masternodes())
        self.num_blocks = min(MAX_BLOCKS, self.num_mnodes)
        self.sub_blocks_per_block = (self.num_mnodes + self.num_blocks - 1) // self.num_blocks
        self.num_sb_builders = min(MAX_SUB_BLOCK_BUILDERS, self.sub_blocks_per_block)
        self.my_sb_index = self._get_my_index() % self.sub_blocks_per_block

        self.log.notice("\nBlockManager initializing with\nvk={vk}\nsubblock_index={sb_index}\n"
                        "num_masternodes={num_mn}\nnum_blocks={num_blocks}\nsub_blocks_per_block={sb_per_block}\n"
                        "num_sb_builders={num_sb_builders}\n"
                        .format(vk=self.verifying_key, sb_index=self.my_sb_index, num_mn=self.num_mnodes,
                                num_blocks=self.num_blocks, sb_per_block=self.sub_blocks_per_block,
                                num_sb_builders=self.num_sb_builders))
        assert self.num_mnodes >= self.num_blocks, "num_blocks cannot be more than num_masternodes"

        self.sbb_map = self._build_sbb_map()
        self.log.info("Using sub-block builder map {}".format(self.sbb_map))

        # Define Sockets (these get set in build_task_list)
        self.ipc_router, self.pub, self.sub = None, None, None
        self.ipc_ip = IPC_IP + '-' + str(os.getpid())

        self.run()
        self.log.critical("just called run!".format())

    def run(self):
        # DEBUG TODO DELETE
        self.log.critical("\n!!!! RUN CALLED !!!!!\n")
        # END DEBUG
        self.build_task_list()
        self.start_sbb_procs()
        self.log.info("Block Manager starting...")
        self.loop.run_until_complete(asyncio.gather(*self.tasks))

    def build_task_list(self):
        # Create ROUTER socket for bidirectional communication with SBBs over IPC
        self.ipc_router = self.manager.create_socket(socket_type=zmq.ROUTER, name="BM-IPC-Router")
        self.ipc_router.bind(port=IPC_PORT, protocol='ipc', ip=self.ipc_ip)
        self.tasks.append(self.ipc_router.add_handler(self.handle_ipc_msg))

        # Create SUB socket to
        # 1) listen for subblock contenders from other delegates
        # 2) listen for NewBlockNotifications from masternodes
        self.sub = self.manager.create_socket(socket_type=zmq.SUB, name="BM-Sub")  # TODO secure him
        self.tasks.append(self.sub.add_handler(self.handle_sub_msg))

        # Listen to other delegates (NOTE: with no filter currently)
        self.sub.setsockopt(zmq.SUBSCRIBE, b'')
        for vk in VKBook.get_delegates():
            if vk != self.verifying_key:  # Do not SUB to itself
                self.sub.connect(vk=vk, port=INTER_DELEGATE_PORT)

        # Listen to Masternodes
        self.sub.setsockopt(zmq.SUBSCRIBE, MASTERNODE_DELEGATE_FILTER.encode())
        for vk in VKBook.get_masternodes():
            self.sub.connect(vk=vk, port=MN_NEW_BLOCK_PUB_PORT)

    def make_new_sub(self):
        self.sub = self.manager.create_socket(socket_type=zmq.SUB)  # TODO secure him
        self.sub.bind()

    def start_sbb_procs(self):
        for i in range(self.num_sb_builders):
            self.sb_builders[i] = LProcess(target=SubBlockBuilder,
                                           kwargs={"ipc_ip": self.ipc_ip, "ipc_port": IPC_PORT,
                                                   "signing_key": self.signing_key, "ip": self.ip,
                                                   "sbb_map": self.sbb_map, "sbb_index": i,
                                                   "num_sb_builders": self.num_sb_builders})
            self.log.info("Starting SBB #{}".format(i))
            self.sb_builders[i].start()

    def _build_mn_indices(self):
        # For convenience, we define a bidirectional mapping between Masternode indices and their VKs
        idxs = {vk: index for index, vk in enumerate(VKBook.get_masternodes())}
        reverse_map = dict([reversed(i) for i in idxs.items()])
        idxs.update(reverse_map)

        return idxs

    def _get_my_index(self):
        for index, vk in enumerate(VKBook.get_delegates()):
            if vk == self.verifying_key:
                return index

        raise Exception("Delegate VK {} not found in VKBook {}".format(self.verifying_key, VKBook.get_delegates()))

    def _build_sbb_map(self) -> dict:
        """
        The goal with this mapping is to tell each SBB process which witnesses it should be listening to. This builds a
        mapping of SBB indices to another mapping of MN VKs to witness sets.
        """
        mn_per_sbb = self.num_mnodes // self.num_sb_builders
        sbb_map = {}

        for sbb_idx in range(self.num_sb_builders):
            mn_map = {}
            sbb_map[sbb_idx] = mn_map

            for mn_idx in range(sbb_idx * mn_per_sbb, sbb_idx * mn_per_sbb + mn_per_sbb):
                mn_vk = self.mn_indices[mn_idx]
                mn_map[mn_vk] = self._get_witnesses_for_mn(mn_vk)

        return sbb_map

    def _get_witnesses_for_mn(self, mn_vk) -> list:
        """
        Returns a list of witness VKs that are responsible for relays a given masternode's transactions
        :param mn_vk: The verifying key of the masternode. Must exist in VKBook
        """
        assert mn_vk in VKBook.get_masternodes(), "mn_vk {} not in VKBook {}".format(mn_vk, VKBook.get_masternodes())
        assert mn_vk in MN_WITNESS_MAP, "MN VK {} not in MN_WITNESS_MAP {}".format(mn_vk, MN_WITNESS_MAP)

        return MN_WITNESS_MAP[mn_vk]

    def handle_ipc_msg(self, frames):
        # This callback should receive stuff from everything on self.ipc_router. Currently, this is just the SBB procs
        self.log.important("Got msg over ROUTER IPC from a SBB with frames: {}".format(frames))  # TODO delete this

        # First frame, frames[0], is the ID frame, last frame frames[-1] is the message binary. Since this is over IPC,
        # this does not necessarily have to be an Envelope.

        # DEBUG TODO DELETE
        # (Just for testing) we reply to that msg
        id_frame, msg = frames[0], frames[-1].decode()
        reply_msg = "Thanks for the msg {}".format(msg)
        self.ipc_router.send_multipart([id_frame, reply_msg.encode()])
        # END DEBUG

    def handle_sub_msg(self, frames):
        # This handle will get NewBlockNotifications from Masternodes, and BlockContenders (or whatever the equivalent
        # is now) from Delegates

        # The first frame is the filter, and the last frame is the envelope binary
        envelope = Envelope.from_bytes(frames[-1])  # TODO envelope validation
        msg = envelope.message
        msg_hash = envelope.message_hash

        if isinstance(msg, NewBlockNotification):
            self.handle_new_block(envelope)
        elif isinstance(msg, BlockContender):
            # TODO implement
            # self.recv_merkle_tree(event)
            self.recv_sub_block(msg)
        else:
            raise Exception("BlockManager got message type {} from SUB socket that it does not know how to handle"
                            .format(type(msg)))
        # Last frame, frames[-1] will be the envelope binary

    def handle_new_block(self, envelope: Envelope):
        cur_block_hash, cur_timestamp = self.get_latest_block_hash_timestamp()
        block_hash, timestamp = self.fetch_hash_timestamp(envelope)
        if (block_hash == self.cur_block_hash) or (timestamp < self.cur_timestamp):
            # TODO log something
            pass

        num = self.next_block.get(block_hash, 0) + 1
        if (num == self.quorum):
            self.update_db(envelope.message)
            self.next_block.remove(block_hash)
        else:
            self.next_block[block_hash] = num


    # def _build_task_list(self):
    #     # Add router socket - where do we listen to this ?? add
    #     socket = ZmqAPI.add_router(ip=self.ip)
    #     self.sockets.append(socket)
    #     self.tasks.append(self._listen_to_router(socket))
    #
    #     socket = ZmqAPI.get_socket(self.verifying_key, type=zmq.SUB)
    #     self.sockets.append(socket)
    #     # now build listening task to other delegate(s)
    #     for vk in VKBook.get_delegates():
    #         if vk != self.verifying_key:  # not to itself
    #             socket.connect(vk=vk)
    #     self.tasks.append(self._sub_to_delegate(socket))
    #
    #     # first build master(s) listening tasks
    #     self.build_masternode_indices()  # builds mn_indices
    #     mn_socket = ZmqAPI.get_socket(self.verifying_key, type=zmq.SUB)
    #     self.dealer = ZmqAPI.get_socket(self.verifying_key, type=zmq.DEALER)
    #     for vk, index in self.mn_indices:
    #         # ip = OverlayInterface::get_node_from_vk(vk)
    #         # sub connection
    #         mn_socket.connect(vk=vk, filter=MASTERNODE_DELEGATE_FILTER, port=MN_NEW_BLOCK_PUB_PORT))
    #
    #         # dealer connection
    #         self.dealers.connect(vk)
    #
    #         self.sockets.append(mn_socket)
    #         self.tasks.append(self._sub_to_master(mn_socket, vk, index)
    #
    #     for index in range(self.num_sb_builders):
    #         # create sbb processes and sockets
    #         self.sbb_ports[index] = port = 6000 + index  # 6000 -> SBB_PORT
    #         self.sb_builders[index] = Process(target=SubBlockBuilder,
    #                                           args=(self.signing_key, self.url,
    #                                                 self.sbb_ports[index],
    #                                                 index))  # we probably don't need to pass port if we pass index
    #         self.sb_builders[index].start()
    #         socket = ZmqAPI.get_socket(self.verifying_key, socket_type=zmq.PAIR)
    #         socket.connect("{}:{}".format(url, port)))
    #         self.sockets.append(socket)
    #         self.tasks.append(self._listen_to_sbb(socket, vk, index)


    # async def _sub_to_delegate(self, socket, vk):
    #     while True:
    #         event = await socket->recv_event()
    #
    #         if event == MERKLE_SUB_BLOCK:
    #             self.recv_merkle_tree(event)
    #         # elif
    #
    #
    # async def _sub_to_master(self, socket, mn_vk, mn_index):
    #     # Events:
    #     # 1. recv new block notification
    #     last_block_hash, last_timestamp = self.get_latest_block_hash_timestamp()
    #     next_block = {}
    #
    #     while True:
    #         event = await socket->recv_event()
    #
    #         if event == NEW_BLOCK:
    #             block_hash, timestamp = self.fetch_hash_timestamp(event)
    #             if (block_hash == last_block_hash) or (timestamp < last_timestamp):
    #                 continue
    #             num = next_block.get(block_hash, 0) + 1
    #             if (num == self.quorum):
    #                 self.update_db(event)
    #                 next_block = {}
    #             else:
    #                 next_block[block_hash] = num
    #
    #
    # async def _listen_to_sbb(socket, vk, index):
    #     # Events:
    #     # 1. recv merkle sub-block from SB builders
    #     while True:
    #         event = await socket->recv_event()
    #
    #         if event == MERKLE_SUB_BLOCK:
    #             if index == self.my_sb_index:  # responsbile for this sub-block
    #                 self.handle_sub_block(event)  # verify and publish to masters and other delegates
    #         # elif
    #
    #

    #
    # def handle_sub_block(self, sub_block, index):
    #     # resolve conflicts if any with previous sub_blocks
    #     sub_block = self.resolve_conflicts(sub_block, index)
    #     # keep it in
    #     self.save_and_vote(sub_block, index)
    #
    #
    # def save_and_vote(self, sub_block, index):
    #     if index == self.my_sb_index:
    #         self.publish_sub_block(sub_block)  # to masters and other delegates
    #     else:
    #         other_sb = self.pending_sigs.get(index, None)
    #         if (other_sb == None):
    #             self.my_sub_blocks[index] = sub_block
    #         else:
    #             status = self.vote(other_sb, sub_block)
    #             if status:
    #                 self.pending_sigs[index] = None
    #             else:
    #                 self.my_sub_blocks[index] = sub_block
    #
    #

    def vote(self, other_sb, sub_block):
        # check first if they have same input txns
        bag_hash1 = other_sb.get_bag_hash()
        bag_hash2 = sub_block.get_bag_hash()
        if (bag_hash1 != bag_hash2):
            return False
        ms_hash1 = other_sb.get_root_hash()
        ms_hash2 = sub_block.get_root_hash()
        agreed = (ms_hash1 == ms_hash2)
        publish_vote(agree if agreed else disagree)  # to all masters
        return agreed
    
   
    def recv_sub_block(self, other_sb):
        index = self.get_sub_block_index(other_sb)
        sub_block = self.my_sub_blocks.get(index, None)
        if (sub_block == None):
            self.pending_sigs[index] = other_sb
        else:
            status = self.vote(other_sb, sub_block)
            if status:
                self.my_sub_blocks[index] = None
            else:
                self.pending_sigs[index] = other_sb
