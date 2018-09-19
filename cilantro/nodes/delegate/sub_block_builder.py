"""
    SubBlockBuilder

    Conceptually Sub Block could form whole block or part of block. This lets us scale things horizontally.
    Each of this builder will be started on a separate process and will assume BlockManager would be 
    responsible to resolve db conflicts (due to ordering of these sub-blocks at block level) and 
    send resolved subtree to master (and other delegates).
    it will send its vote on other subblocks to master directly.
    
    We will make each SubBlockBuilder responsible for one master and so in our case, we will have 64 processes,
    each producing a sub-block. We can form one block with 8/16 sub-blocks so we will have 8/4 independent blocks.
    1 master    -> 1 subblcok
    2 subblocks -> 1 subtree
    8 subtrees  -> 1 block
    64 masters -> 64 sub-blocks -> 32 subtrees -> 4 blocks
    
    SubBlockBuilder
      Input: set of witnesses that provide transactions from a single master
             need to use proxies for zmq communication as witnesses are dynamically rotated to help different masters
             connection port to BlockManager
      0. Opens a subscribe connection to witness pool (thread1)
         just put them in a queue 
      1. Initialization: establish connections to blockmgr (the main process that launched this one)
         when asked to start making a new subblock (blkMgr)
         2. pull next batch from queue (Seneca interface and cost of db access is included here)
         3. Failed contracts have to be in pending state to be resolved
         4. if some failed contracts, resolve or reject them or push them to next block (communication cost to BlkMgr here)
         5. Also BlockMgr may send in new failures (communication cost)
         6. Make and send subblock to blockMgr
"""

# each sbb:
#    - 16 processes -> each process with 4 threads ?? 4 master bins ??
#       rotate circularly
#         thread1 -> take first batch and interpret it and send it. do a small yield??
#         thread2 -> take second batch and repeat

# need to clean this up - this is a dirty version of trying to separate out a sub-block builder in the old code
import asyncio
import zmq.asyncio
from cilantro.logger import get_logger
import signal, sys
from cilantro.storage.db import VKBook
from cilantro.constants.protocol import DUPE_TABLE_SIZE
from cilantro.constants.ports import SBB_PORT_START

from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.consensus.merkle_signature import MerkleSignature

from cilantro.protocol.interpreter import SenecaInterpreter
from cilantro.protocol import wallet
from cilantro.protocol.structures import CappedSet
from cilantro.protocol.structures.linked_hashtable import LinkedHashTable
from cilantro.protocol.structures import MerkleTree
from cilantro.protocol.multiprocessing.worker import Worker

from typing import Union
from cilantro.utils.hasher import Hasher

# need delegate communication class to describe events
#  all currently known hand-shakes of block making
#  get # of txns
#  move to block state. may skip some due to low vol of txns there.
# need block state events
#    for 4 blocks:
#       blocks in 1 and 2 stages, just do io (no cpu - to make sure cpu is available for other proceses)
#                just txns from witness and drop it in queue  - may keep a count of # of txns
# witness will use master router/dealer to communicate it is going to cover it. can master accept/reject it?
# master will publish it once it accepts
# witness can quit at a certain time interval ?? and delegates can kick it out once it has other 5/6 copies and no data from it??


class SubBlockBuilder(Worker):
    def __init__(self, ip: str, signing_key: str, ipc_ip: str, ipc_port: int, sbb_index: int, sbb_map: dict,
                 num_sb_builders: int, *args, **kwargs):
        super().__init__(signing_key=signing_key, name="SubBlockBuilder_{}".format(sbb_index))

        self.ip = ip
        self.sbb_index, self.sbb_map = sbb_index, sbb_map

        self.block_num = int(sbb_index / 16)       # hard code this for now
        self.sub_block_num = int(sbb_index % 16)

        self.num_txs = 0
        self.num_sub_blocks = 0
        self.tasks = []

        self.pending_txs = LinkedHashTable()
        self.interpreter = SenecaInterpreter()
        self._recently_seen = CappedSet(max_size=DUPE_TABLE_SIZE)  # TODO do we need this?

        # Create DEALER socket to talk to the BlockManager process over IPC
        self.dealer = None
        self._create_dealer_ipc(port=ipc_port, ip=ipc_ip, identity=str(self.sbb_index).encode())

        # BIND sub sockets to listen to witnesses
        self.subs = []
        self._create_sub_sockets(num_sb_builders=num_sb_builders, num_mnodes=len(VKBook.get_masternodes()))

        # Create a Seneca interpretter for this SBB
        self.interpreter = SenecaInterpreter()

        # DEBUG TODO DELETE
        self.tasks.append(self.test_dealer_ipc())
        # END DEBUG

        self.run()

    def run(self):
        self.log.notice("SBB {} starting...".format(self.sbb_index))
        self.loop.run_until_complete(asyncio.gather(*self.tasks))

    async def test_dealer_ipc(self):
        self.log.info("Spamming BlockManager over IPC...")
        while True:
            msg = "hello from SBB {}".format(self.sbb_index)
            self.log.debug("Sending msg {}".format(msg))
            self.dealer.send_multipart([msg.encode()])
            await asyncio.sleep(16)

    def _create_dealer_ipc(self, port: int, ip: str, identity: bytes):
        self.log.info("Connecting to BlockManager's ROUTER socket with a DEALER using ip {}, port {}, and id {}"
                      .format(port, ip, identity))
        self.dealer = self.manager.create_socket(socket_type=zmq.DEALER, name="SBB-IPC-Dealer[{}]".format(self.sbb_index))
        self.dealer.setsockopt(zmq.IDENTITY, identity)
        self.dealer.connect(port=port, protocol='ipc', ip=ip)
        self.tasks.append(self.dealer.add_handler(handler_func=self.handle_ipc_msg))

    def _create_sub_sockets(self, num_sb_builders, num_mnodes):
        # First, determine the set of Masternodes this SBB is responsible for
        num_mn_per_sbb = num_mnodes // num_sb_builders
        mn_range = list(range(self.sbb_index * num_mn_per_sbb, self.sbb_index * num_mn_per_sbb + num_sb_builders))
        self.log.info("This SBB is responsible for masternodes in index range {}".format(self.sbb_index, mn_range))

        # We then BIND a sub socket to a port for each of these masternode indices
        for mn_idx in mn_range:
            port = SBB_PORT_START + mn_idx
            self.log.info("SBB BINDing to port {} with no filter".format(port))
            sub = self.manager.create_socket(socket_type=zmq.SUB, name="SBB-Sub[{}]-{}".format(self.sbb_index, mn_idx))
            sub.setsockopt(zmq.SUBSCRIBE, b'')
            sub.bind(port=port, ip=self.ip)  # TODO secure him
            self.tasks.append(sub.add_handler(handler_func=self.handle_sub_msg))
            self.subs.append(sub)

    def handle_ipc_msg(self, frames):
        self.log.important("Got msg over Router IPC from BlockManager with frames: {}".format(frames))
        # TODO implement

    def handle_sub_msg(self, frames):
        self.log.important("Sub socket got frames {}".format(frames))


    # # will it receive the list from BM - no need to know upfront
    # # still need to figure out starting point where it has all the witnesses available - may not be up front
    # # also need to allow for the case where it will handle multiple masters (multiple sets of witnesses - format??)
    # def _parse_witness_list(self, witness_list_list):
    #     witness_lists = witness_list_list.split(";")
    #     for index, witness_list in enumerate(witness_lists):
    #         witnesses = witness_list.split(",")
    #         for witness in witnesses:
    #             ip, vk = witness.split(":", 1)
    #             self.witness_table[index][vk] = []
    #             self.witness_table[index][vk].append(ip)
          
    # delegates bind to sub sockets on a fixed port. Each witness can open its pub socket and connect to all sub sockets??
    # def _subscribe_to_witnesses(self):
    #     for index, tbl in enumerate(self.witness_table):
    #         socket = ZmqAPI.get_socket(self.verifying_key, type=zmq.SUB)
    #         for vk, value in self.witness_table:
    #             ip = value[0]
    #             url = "{}:{}".format(ip, PUB_SUB_PORT)
    #             socket.connect(vk=vk, ip=ip)
    #             self.log.debug("Connected to witness at ip:{} socket:{}"
    #                            .format(ip, witness_vk))
    #         self.witness_table[vk].append(socket)
    #         self.tasks.append(self._listen_to_witness(socket, index))

    # TODO mimic this logic in handle_ipc_msg
    # async def _listen_to_block_manager(self):
    #     try:
    #         self.log.debug(
    #            "Sub-block builder {} listening to Block-manager process at {}"
    #            .format(self.sbb_index, self.url))
    #         while True:
    #             cmd_bin = await self.socket.recv()
    #             self.log.debug("Got cmd from BM: {}".format(cmd_bin))
    #
    #             # need to change logic here based on our communication protocols
    #             if cmd_bin == KILL_SIG:
    #                 self.log.debug("Sub-block builder {} got kill signal"
    #                 .format(self.sbb_index))
    #                 self._teardown()
    #                 return
    #
    #             if cmd_bin == ADD_WITNESS:
    #                 # new witness that will cover the master
    #                 # witness_vk, master_vk
    #
    #             # SKIP_ROUND behavior is captured by this guy receiving an empty bag
    #             # if cmd_bin == SKIP_ROUND:
    #             #     skip if don't have txns pending
    #
    #             if cmd_bin == CANCEL_SUBTREE:
    #                 if self._interpret:
    #                     self._interpret = 0
    #
    #
    #     except asyncio.CancelledError:
    #         self.log.warning("Builder _recv_messages task canceled externally")


    # async def recv_multipart(self, socket, callback_fn: types.MethodType, ignore_first_frame=False):
    async def _listen_to_witness(self, socket, index):
        self.log.debug("Sub-block builder {} listening to witness set {}"
                       .format(self.sbb_index, index))
        last_bag_hash = 0
        last_time_stamp = 0

        while True:

            event = await socket.recv_event()

            if event == TXN_BAG:
                bag_hash, timestamp = self.fetch_hash_timestamp(event)
                if (bag_hash == last_bag_hash) or (timestamp < last_timestamp):
                    continue
                last_bag_hash = bag_hash
                last_time_stamp = timestamp
                txn_bag = event.fetch_bag()
                self.pending_txs[index].append(bag_hash, txn_bag)

    async def _interpret_next_subtree(self, index):
        self.log.debug("Starting to make a new sub-block {} for block {}"
                       .format(self.sub_block_num, self.block_num))
        # get next batch of txns ??  still need to decide whether to unpack a bag or check for end of txn batch
        txn_bag = self.pending_txs[index].popleft()
        if txn_bag.empty():
            return false
        
        for txn in txn_bag:
            self.interpreter.interpret(txn)  # this is a blocking call. either async or threads??

        # Merkle-ize transaction queue and create signed merkle hash
        all_tx = self.interpreter.queue_binary
        self.merkle = MerkleTree.from_raw_transactions(all_tx)
        self.signature = wallet.sign(self.signing_key, self.merkle.root)

        # Create merkle signature message and publish it
        merkle_sig = MerkleSignature.create(sig_hex=self.signature,
                                            timestamp='now',
                                            sender=self.verifying_key)
        self.send_signature(merkle_sig)  # send signature to block manager

    def send_signature(self, merkle_sig):
        self.socket.send(merkle_sig.serialize())


