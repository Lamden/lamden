"""
    SubBlockBuilder

    If Block is viewed as consists of a merkle tree of transactions, then sub-block refers to the sub-tree of the block.
    Conceptually Sub Block could form whole block or part of block. This lets us scale things horizontally.
    Each of this SB builder will be started on a separate process and will coordinate with BlockManager 
    to resolve db conflicts between sub-blocks and send resolved sub-block to master.
    It also sends in partial data of transactions along with the sub-block
    
    We typically take all transactions from a single master to form a sub-block,
    but a sub-block builder can be responsible for more than one master and so can make more than one sub-block.
    This ensures our ordering guarantees that transactions entered at a master is executed in that order, 
    but we will decide the order of transactions between different masters.
    
"""


# need to clean this up - this is a dirty version of trying to separate out a sub-block builder in the old code
import asyncio
import zmq.asyncio
import time
from typing import List

from cilantro.logger import get_logger
from cilantro.storage.db import VKBook
from cilantro.constants.ports import SBB_PORT_START

from cilantro.messages.base.base import MessageBase
from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.consensus.merkle_signature import MerkleSignature
from cilantro.messages.consensus.sub_block_contender import SubBlockContender
from cilantro.messages.transaction.batch import TransactionBatch
from cilantro.messages.signals.make_next_block import MakeNextBlock
from cilantro.messages.consensus.empty_sub_block_contender import EmptySubBlockContender

from cilantro.protocol.interpreter import SenecaInterpreter
from cilantro.protocol import wallet
from cilantro.protocol.multiprocessing.worker import Worker

from cilantro.protocol.structures import MerkleTree
from cilantro.protocol.structures.linked_hashtable import LinkedHashTable

from cilantro.utils.hasher import Hasher
from cilantro.utils.utils import int_to_bytes, bytes_to_int

from cilantro.constants.system_config import *

# This is a convenience struct to hold all data related to a sub-block in one place.
# Since we have more than one sub-block per process, SBB'er will hold an array of SubBlockManager objects
class SubBlockManager:
    def __init__(self, sub_block_index: int, sub_socket, processed_txs_timestamp: int=0):
        self.sub_block_index = sub_block_index
        self.sub_socket = sub_socket
        self.processed_txs_timestamp = processed_txs_timestamp
        self.pending_txs = LinkedHashTable()
        self.num_pending_sb = 0
        self.merkle = None


class SubBlockBuilder(Worker):
    def __init__(self, ip: str, signing_key: str, ipc_ip: str, ipc_port: int, sbb_index: int, *args, **kwargs):
        super().__init__(signing_key=signing_key, name="SubBlockBuilder_{}".format(sbb_index))

        self.ip = ip
        self.sbb_index = sbb_index
        self.cur_block_index = NUM_BLOCKS - 1  # so it will start at block 0
        self.pending_block_index = 0
        self.interpreter = SenecaInterpreter()

        self.tasks = []

        # Create DEALER socket to talk to the BlockManager process over IPC
        self.ipc_dealer = None
        self._create_dealer_ipc(port=ipc_port, ip=ipc_ip, identity=str(self.sbb_index).encode())

        # BIND sub sockets to listen to witnesses
        self.sb_managers = []
        self._create_sub_sockets()

        # DEBUG -- TODO DELETE
        # self.tasks.append(self.spam_bm())
        # END DEBUG

        self.log.notice("sbb_index {} tot_sbs {} num_blks {} num_sb_per_blder {} num_sb_per_block {} num_sb_per_builder {}"
                        .format(sbb_index, NUM_SUB_BLOCKS, NUM_BLOCKS, NUM_SB_BUILDERS, NUM_SB_PER_BLOCK, NUM_SB_PER_BUILDER))

        self.run()

    async def spam_bm(self):
        while True:
            await asyncio.sleep(4)
            msg = 'hello from sbb {}'.format(self.sbb_index)
            self.log.info("SBB sending msg over ipc: {}".format(msg))
            self.ipc_dealer.send_multipart([b'0', msg.encode()])

    def run(self):
        self.log.notice("SBB {} starting...".format(self.sbb_index))
        self.loop.run_until_complete(asyncio.gather(*self.tasks))

        # DEBUG -- TODO DELETE
        self.log.fatal("\n SBB EXITING EVENT LOOP!!! THIS SHOULD NOT HAPPEN!!! \n")
        # END DEBUG

    def _create_dealer_ipc(self, port: int, ip: str, identity: bytes):
        self.log.info("Connecting to BlockManager's ROUTER socket with a DEALER using ip {}, port {}, and id {}"
                      .format(ip, port, identity))
        self.ipc_dealer = self.manager.create_socket(socket_type=zmq.DEALER, name="SBB-IPC-Dealer[{}]".format(self.sbb_index), secure=False)
        self.ipc_dealer.setsockopt(zmq.IDENTITY, identity)
        self.ipc_dealer.connect(port=port, protocol='ipc', ip=ip)

        self.tasks.append(self.ipc_dealer.add_handler(handler_func=self.handle_ipc_msg))

    def _create_sub_sockets(self):
        # We then BIND a sub socket to a port for each of these masternode indices
        for idx in range(NUM_SB_PER_BUILDER):
            sb_idx = idx * NUM_SB_BUILDERS + self.sbb_index  # actual SB index in global index space
            if sb_idx >= NUM_SUB_BLOCKS:    # out of range already
                return

            port = SBB_PORT_START + sb_idx
            sub = self.manager.create_socket(socket_type=zmq.SUB, name="SBB-Sub[{}]-{}".format(self.sbb_index, sb_idx),
                                             secure=True)
            sub.setsockopt(zmq.SUBSCRIBE, b'')
            sub.bind(port=port, ip=self.ip)
            self.log.info("SBB BINDing to port {} with no filter".format(port))

            self.sb_managers.append(SubBlockManager(sub_block_index=sb_idx, sub_socket=sub))
            self.tasks.append(sub.add_handler(handler_func=self.handle_sub_msg, handler_key=idx))

    def handle_ipc_msg(self, frames):
        # DEBUG -- TODO DELETE
        # self.log.important("Got msg over Dealer IPC from BlockManager with frames: {}".format(frames))  # TODO remove
        # return
        # END DEBUG
        self.log.spam("Got msg over Dealer IPC from BlockManager with frames: {}".format(frames))
        assert len(frames) == 2, "Expected 3 frames: (msg_type, msg_blob). Got {} instead.".format(frames)

        msg_type = bytes_to_int(frames[0])
        msg_blob = frames[1]

        msg = MessageBase.registry[msg_type].from_bytes(msg_blob)
        self.log.debugv("SBB received an IPC message {}".format(msg))

        # raghu TODO listen to updated DB message from BM and start conflict resolution if any
        # call to make sub-block(s) for next block
        # tie with messages below

        if isinstance(msg, MakeNextBlock):
            self._make_next_sub_block()
        # elif isinstance(msg, DiscardPrevBlock):        # if not matched consensus, then discard current state and use catchup flow
            # self.interpreter.flush(update_state=false)
        else:
            raise Exception("SBB got message type {} from IPC dealer socket that it does not know how to handle"
                            .format(type(msg)))

    def handle_sub_msg(self, frames, index):
# rpc
        self.log.info("Sub socket got frames {} with handler_index {}".format(frames, index))
        assert 0 <= index < len(self.sb_managers), "Got index {} out of range of sb_managers array {}".format(
            index, self.sb_managers)

        envelope = Envelope.from_bytes(frames[-1])
        timestamp = envelope.meta.timestamp
        assert isinstance(envelope.message, TransactionBatch), "Handler expected TransactionBatch but got {}".format(envelope.messages)

        if timestamp <= self.sb_managers[index].processed_txs_timestamp:
            self.log.debug("Got timestamp {} that is prior to the most recent timestamp {} for sb_manager {} tho"
                           .format(timestamp, self.sb_managers[index].processed_txs_timestamp, index))
            return

        input_hash = Hasher.hash(envelope)
        # if the sb_manager already has this bag, ignore it
        if input_hash in self.sb_managers[index].pending_txs:
            self.log.debugv("Input hash {} already found in sb_manager at index {}".format(input_hash, index))
            return

        # TODO properly wrap below in try/except. Leaving it as an assertion just for dev
        assert envelope.verify_seal(), "Could not validate seal for envelope {}!!!".format(envelope)
        # TODO if verification fails, log and return here ?

        # keep updating timestamp as they are increasing from a master

        # DEBUG -- TODO DELETE
        self.log.important("Recv tx batch with input hash {}".format(input_hash))
        # END DEBUG

        self.sb_managers[index].processed_txs_timestamp = timestamp
        if self.sb_managers[index].num_pending_sb > 0:
            if ((self.sb_managers[index].num_pending_sb == 1) and (self.pending_block_index == self.cur_block_index)):
                sbb_idx = self.sb_managers[index].sub_block_index
                self._make_next_sb(input_hash, envelope.message, sbb_idx)

            self.sb_managers[index].num_pending_sb = self.sb_managers[index].num_pending_sb - 1
        else:
            self.log.debug("Queueing transaction batch for sb manager {}. SB_Manager={}".format(index, self.sb_managers[index]))
            self.sb_managers[index].pending_txs.append(input_hash, envelope.message)

    def _make_next_sb(self, input_hash: str, tx_batch: TransactionBatch, sbb_idx: int):
        self.log.debug("SBB {} attempting to build sub block with sub block index {}".format(self.sbb_index, sbb_idx))

        sbc = self._create_empty_sbc(input_hash, sbb_idx) if tx_batch.is_empty \
            else self._create_sbc_from_batch(input_hash, sbb_idx, tx_batch)
        self._send_msg_over_ipc(sbc)

    def _create_empty_sbc(self, input_hash: str, sbb_idx: int) -> SubBlockContender:
        """
        Creates an Empty Sub Block Contender from a TransactionBatch
        """
        self.log.debug("Empty SBB {} sub block index {}".format(self.sbb_index, sbb_idx))
        signature = wallet.sign(self.signing_key, input_hash.encode())
        merkle_sig = MerkleSignature.create(sig_hex=signature,
                                            timestamp=str(int(time.time())),
                                            sender=self.verifying_key)
        sbc = EmptySubBlockContender.create(input_hash=input_hash,
                                            sb_index=sbb_idx, signature=merkle_sig)
        return sbc

    def _create_sbc_from_batch(self, input_hash: str, sbb_idx: int,
                               batch: TransactionBatch) -> SubBlockContender:
        """
        Creates a Sub Block Contender from a TransactionBatch
        """
        # We assume if we are trying to create a SBC, our interpreter is empty and in a fresh state
        # assert self.interpreter.queue_size == 0, "Expected an empty interpreter queue before building a SBC"
        num_txs = len(batch.transactions)
        self.log.debug("True SBB {} sub block index {}".format(self.sbb_index, sbb_idx))

        for txn in batch.transactions:
            self.interpreter.interpret(txn)  # this is a blocking call. either async or threads??

        # Merkle-ize transaction queue and create signed merkle hash
        all_tx_queue = self.interpreter.get_tx_queue()
        tx_queue = all_tx_queue[-num_txs:]
        tx_binaries = [tx.serialize() for tx in tx_queue]

        # TODO -- do we want to sign the real 'raw' merkle root or the merkle root as an encoded hex str???
        merkle = MerkleTree.from_raw_transactions(tx_binaries)
        signature = wallet.sign(self.signing_key, merkle.root)
        merkle_sig = MerkleSignature.create(sig_hex=signature,
                                            timestamp=str(time.time()),
                                            sender=self.verifying_key)

        sbc = SubBlockContender.create(result_hash=merkle.root_as_hex, input_hash=input_hash,
                                       merkle_leaves=merkle.leaves, sub_block_index=sbb_idx,
                                       signature=merkle_sig, transactions=tx_queue)
        return sbc

    def _send_msg_over_ipc(self, message: MessageBase):
        """
        Convenience method to send a MessageBase instance over IPC dealer socket. Includes a frame to identify the
        type of message
        """
        assert isinstance(message, MessageBase), "Must pass in a MessageBase instance"
        message_type = MessageBase.registry[type(message)]  # this is an int (enum) denoting the class of message
        self.ipc_dealer.send_multipart([int_to_bytes(message_type), message.serialize()])

    def _make_next_sub_block(self):
        # first commit current state - under no conflict between SB assumption (TODO)
        self.log.info("Flushing interpreter queue")
        self.interpreter.flush()

        # now start next one
        self.cur_block_index = (self.cur_block_index + 1) % NUM_BLOCKS
        sb_index_start = self.cur_block_index * NUM_SB_PER_BLOCK
        for i in range(NUM_SB_PER_BLOCK):
            sb_idx = sb_index_start + i
            if sb_idx >= len(self.sb_managers):    # out of range already
                return

            if len(self.sb_managers[sb_idx].pending_txs) > 0:
                input_hash, txs_bag = self.sb_managers[sb_idx].pending_txs.pop_front()
                sbb_idx = self.sb_managers[sb_idx].sub_block_index
                self._make_next_sb(input_hash, txs_bag, sbb_idx)
            else:
                self.sb_managers[sb_idx].num_pending_sb = self.sb_managers[sb_idx].num_pending_sb + 1
                self.pending_block_index = self.cur_block_index


