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
from cilantro.messages.transaction.batch import TransactionBatch

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

class SubBlockManager:
    def __init__(self, sub_block_index: int, sub_socket, processed_txs_timestamp: int=0):
        self.processed_txs_timestamp, self.sub_block_index = processed_txs_timestamp, sub_block_index
        self.pending_txs = LinkedHashTable()
        self.sub_socket = sub_socket

class SubBlockBuilder(Worker):
    def __init__(self, ip: str, signing_key: str, ipc_ip: str, ipc_port: int, sbb_index: int,
                 num_sb_builders: int, num_sb_per_block: int, num_blocks: int, *args, **kwargs):
        super().__init__(signing_key=signing_key, name="SubBlockBuilder_{}".format(sbb_index))

        self.ip = ip
        self.sbb_index = sbb_index
        self.num_sub_blocks_per_block = num_sb_per_block
        self.num_blocks = num_blocks
        self.current_sbm_idx = 0  # The index of the sb_manager whose transactions we are trying to build a SB for

        self.tasks = []

        # Create DEALER socket to talk to the BlockManager process over IPC
        self.dealer = None
        self._create_dealer_ipc(port=ipc_port, ip=ipc_ip, identity=str(self.sbb_index).encode())

        # BIND sub sockets to listen to witnesses
        self.sb_managers = []
        self._create_sub_sockets(num_sb_builders=num_sb_builders)

        # Create a Seneca interpreter for this SBB
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

    def _create_sub_sockets(self, num_sb_builders):
        num_sub_blocks = self.num_sub_blocks_per_block * self.num_blocks

        # We then BIND a sub socket to a port for each of these masternode indices
        for idx in range(num_sub_blocks):
            sb_idx = idx * num_sb_builders + self.sbb_index
            port = SBB_PORT_START + sb_idx

            sub = self.manager.create_socket(socket_type=zmq.SUB, name="SBB-Sub[{}]-{}".format(self.sbb_index, sb_idx))
            sub.setsockopt(zmq.SUBSCRIBE, b'')
            sub.bind(port=port, ip=self.ip)  # TODO secure him
            self.log.info("SBB BINDing to port {} with no filter".format(port))

            self.sb_managers.append(SubBlockManager(sub_block_index=sb_idx, sub_socket=sub))
            self.tasks.append(sub.add_handler(handler_func=self.handle_sub_msg, handler_key=idx))

    def handle_ipc_msg(self, frames):
        self.log.important("Got msg over Router IPC from BlockManager with frames: {}".format(frames))
        # TODO implement

    def handle_sub_msg(self, frames, index):
        self.log.info("Sub socket got frames {} with handler_index {}".format(frames, index))
        assert 0 <= index < len(self.sb_managers), "Got index {} out of range of sb_managers array {}".format(
            index, self.sb_managers)

        envelope = Envelope.from_bytes(frames[-1])
        timestamp = envelope.meta.timestamp
        assert isinstance(envelope.message, TransactionBatch), "Handler expected TransactionBatch but got {}".format(envelope.messages)

        if timestamp < self.sb_managers[index].processed_txs_timestamp:
            self.log.critical("Got timestamp {} that is prior to the most recent timestamp {} for sb_manager {}! BRUH"
                              .format(timestamp, self.sb_managers[index].processed_txs_timestamp, index))
            return

        msg = envelope.message
        msg_hash = envelope.message_hash
        # if the sb_manager already has this bag, ignore it
        # if self.sb_managers[index].pending_txs.find(msg_hash):
        if msg_hash in self.sb_managers[index]:
            self.log.debugv("Msg hash {} already found in sb_manager at index {}".format(msg_hash, index))
            return

        # now do envelope validation here - TODO

        self.sb_managers[index].pending_txs.append(msg_hash, msg)


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
    #     except asyncio.CancelledError:
    #         self.log.warning("Builder _recv_messages task canceled externally")


    async def _interpret_next_subtree(self):
        self.log.debug("SBB {} attempting to build sub block with sub block manager index {}".format(self.sbb_index, self.current_sbm_idx))
        # get next batch of txns ??  still need to decide whether to unpack a bag or check for end of txn batch

        txn_bag = self.sb_managers[self.current_sbm_idx].pending_txs.popleft()
        if not txn_bag:
            self.log.debugv("Subblock manager at index {} has no TransactionBatches to process".format(self.current_sbm_idx))
        if txn_bag.is_empty:
            self.log.debugv("Subblock manager at index {} got an empty transaction bag!".format(self.current_sbm_idx))
            self.current_sbm_idx = (self.current_sbm_idx + 1) % len(self.sb_managers)

        
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


