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
from cilantro.storage.vkbook import VKBook
from cilantro.storage.state import StateDriver
from cilantro.constants.ports import SBB_PORT_START

from cilantro.messages.base.base import MessageBase
from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.consensus.merkle_signature import MerkleSignature
from cilantro.messages.consensus.sub_block_contender import SubBlockContender
from cilantro.messages.consensus.align_input_hash import AlignInputHash
from cilantro.messages.transaction.batch import TransactionBatch
from cilantro.messages.transaction.data import TransactionData
from cilantro.messages.signals.delegate import MakeNextBlock, DiscardPrevBlock

from seneca.engine.client import NUM_CACHES
from seneca.engine.client import SenecaClient
from seneca.engine.conflict_resolution import CRContext
from cilantro.protocol import wallet
from cilantro.protocol.multiprocessing.worker import Worker

from cilantro.protocol.structures import MerkleTree
from cilantro.protocol.structures.linked_hashtable import LinkedHashTable

from cilantro.utils.hasher import Hasher
from cilantro.utils.utils import int_to_bytes, bytes_to_int

from cilantro.constants.system_config import *
from enum import Enum, unique

@unique
class NextBlockState(Enum):
    NOT_READY  = 0
    READY      = 1
    PROCESSED  = 2

class NextBlockToMake:
    def __init__(self, block_index: int=0, state: NextBlockState=NextBlockState.PROCESSED):
        self.next_block_index = block_index
        self.state = state

# This is a convenience struct to hold all data related to a sub-block in one place.
# Since we have more than one sub-block per process, SBB'er will hold an array of SubBlockManager objects
class SubBlockManager:
    def __init__(self, sub_block_index: int, sub_socket, processed_txs_timestamp: int=0):
        self.sub_block_index = sub_block_index
        self.sub_socket = sub_socket
        self.processed_txs_timestamp = processed_txs_timestamp
        self.pending_txs = LinkedHashTable()
        self.to_finalize_txs = LinkedHashTable()
        self.num_pending_sb = 0


class SubBlockBuilder(Worker):
    def __init__(self, ip: str, signing_key: str, ipc_ip: str, ipc_port: int, sbb_index: int, *args, **kwargs):
        super().__init__(signing_key=signing_key, name="SubBlockBuilder_{}".format(sbb_index))

        self.tasks = []

        self.ip = ip
        self.sbb_index = sbb_index
        self.startup = True
        # self.pending_block_index = -1
        self.client = SenecaClient(sbb_idx=sbb_index, num_sbb=NUM_SB_PER_BLOCK, loop=self.loop)
        # raghu todo may need multiple clients here. NUM_SB_PER_BLOCK needs to be same for all blocks
        # self.clients = []
        # for i in range(NUM_SB_PER_BLOCK_PER_BUILDER):
            # client_sb_index = i * NUM_SB_BUILDERS + sbb_index
            # client = SenecaClient(sbb_idx=client_sb_index, num_sbb=NUM_SB_PER_BLOCK, loop=self.loop)
            # self.clients.append(client)

        # Create DEALER socket to talk to the BlockManager process over IPC
        self.ipc_dealer = None
        self._create_dealer_ipc(port=ipc_port, ip=ipc_ip, identity=str(self.sbb_index).encode())

        # BIND sub sockets to listen to witnesses
        self.sb_managers = []
        self._create_sub_sockets()
        # need to tie with catchup state to initialize to real next_block_to_make
        self._next_block_to_make = NextBlockToMake()

        self.log.notice("sbb_index {} tot_sbs {} num_blks {} num_sb_blders {} num_sb_per_block {} num_sb_per_builder {} sbs_per_blk_per_blder {}"
                        .format(sbb_index, NUM_SUB_BLOCKS, NUM_BLOCKS, NUM_SB_BUILDERS, NUM_SB_PER_BLOCK, NUM_SB_PER_BUILDER, NUM_SB_PER_BLOCK_PER_BUILDER))

        self.run()

    def run(self):
        self.log.notice("SBB {} starting...".format(self.sbb_index))
        self.loop.run_until_complete(asyncio.gather(*self.tasks))

    # raghu todo - call this right after catch up phase, need to figure out the right input hashes though for next block
    def initialize_next_block_to_make(self, next_block_index: int):
        self._next_block_to_make.next_block_index = next_block_index % NUM_BLOCKS
        self._next_block_to_make.state = NextBlockState.READY
        # self._next_block_to_make.state = NextBlockState.READY if self.client.can_start_next_sb \
                                             # else NextBlockState.NOT_READY

    def move_next_block_to_make(self):
        if self._next_block_to_make.state == NextBlockState.PROCESSED:
            self.initialize_next_block_to_make(self._next_block_to_make.next_block_index + 1)
        return self._next_block_to_make.state == NextBlockState.READY

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
            # sidx = idx % NUM_SB_PER_BLOCK_PER_BUILDER
            # sb_idx = sidx * NUM_SB_BUILDERS + self.sbb_index  # SB index for the block

            sb_idx = idx * NUM_SB_BUILDERS + self.sbb_index  # actual SB index in global index space

            port = SBB_PORT_START + sb_idx
            sub = self.manager.create_socket(socket_type=zmq.SUB, name="SBB-Sub[{}]-{}".format(self.sbb_index, sb_idx),
                                             secure=True)
            sub.setsockopt(zmq.SUBSCRIBE, b'')
            sub.bind(port=port, ip=self.ip)
            self.log.info("SBB BINDing to port {} with no filter".format(port))

            self.sb_managers.append(SubBlockManager(sub_block_index=sb_idx, sub_socket=sub))
            self.tasks.append(sub.add_handler(handler_func=self.handle_sub_msg, handler_key=idx))

    def align_input_hashes(self, aih: AlignInputHash):
        self.log.notice("Discarding all pending sub blocks and aligning input hash to {}".format(aih.input_hash))
        self.client.flush_all()
        input_hash = aih.input_hash
        if input_hash in self.sb_managers[0].pending_txs:
            # clear entirely to_finalize
            self.sb_managers[0].to_finalize_txs.clear()
            ih2 = None
            while input_hash != ih2:
                # TODO we may need sb_index if we have more than one sub-block per builder
                ih2, txs_bag = self.sb_managers[0].pending_txs.pop_front()
        elif input_hash in self.sb_managers[0].to_finalize_txs:
            ih2 = None
            while input_hash != ih2:
                # TODO we may need sb_index if we have more than one sub-block per builder
                ih2, txs_bag = self.sb_managers[0].to_finalize_txs.pop_front()
        # at this point, any bags in to_finalize_txs should go back to the front of pending_txs
        while len(self.sb_managers[0].to_finalize_txs) > 0:
            ih, txs_bag = self.sb_managers[0].to_finalize_txs.pop_front()
            self.sb_managers[0].pending_txs.insert_front(ih, txs_bag)
        

    def handle_ipc_msg(self, frames):
        self.log.spam("Got msg over Dealer IPC from BlockManager with frames: {}".format(frames))
        assert len(frames) == 2, "Expected 3 frames: (msg_type, msg_blob). Got {} instead.".format(frames)

        msg_type = bytes_to_int(frames[0])
        msg_blob = frames[1]

        msg = MessageBase.registry[msg_type].from_bytes(msg_blob)
        self.log.debugv("SBB received an IPC message {}".format(msg))


        if isinstance(msg, MakeNextBlock):
            self._make_next_sub_block()

        # if not matched consensus, then discard current state and use catchup flow
        elif isinstance(msg, AlignInputHash):
            self.align_input_hashes(msg)

        else:
            raise Exception("SBB got message type {} from IPC dealer socket that it does not know how to handle"
                            .format(type(msg)))

    def _send_msg_over_ipc(self, message: MessageBase):
        """
        Convenience method to send a MessageBase instance over IPC dealer socket. Includes a frame to identify the
        type of message
        """
        assert isinstance(message, MessageBase), "Must pass in a MessageBase instance"
        message_type = MessageBase.registry[type(message)]  # this is an int (enum) denoting the class of message
        self.ipc_dealer.send_multipart([int_to_bytes(message_type), message.serialize()])

    def handle_sub_msg(self, frames, index):
        self.log.spam("Sub socket got frames {} with handler_index {}".format(frames, index))
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
        if not envelope.verify_seal():
            self.log.critical("Could not validate seal for envelope {}".format(envelope))
            return

        # DEBUG -- TODO DELETE
        self.log.notice("Recv tx batch w/ {} transactions, and input hash {}".format(len(envelope.message.transactions), input_hash))
        # END DEBUG

        self.sb_managers[index].processed_txs_timestamp = timestamp
        self.log.debug("num_pending_txs {}".format(self.sb_managers[index].num_pending_sb))
        self.move_next_block_to_make()
        if self.sb_managers[index].num_pending_sb > 0:
            self.log.debug("Sending transaction batch {} to seneca client".format(index))
            sbb_idx = self.sb_managers[index].sub_block_index
            if self._execute_next_sb(input_hash, envelope.message, sbb_idx):
                self.sb_managers[index].num_pending_sb -= 1
                return
        self.log.debug("Queueing transaction batch for sb manager {}. SB_Manager={}".format(index, self.sb_managers[index]))
        self.sb_managers[index].pending_txs.append(input_hash, envelope.message)

    def _create_empty_sbc(self, cr_context: CRContext):
        """
        Creates an Empty Sub Block Contender
        """
        self.log.info("Building empty sub block contender for input hash {}".format(cr_context.input_hash))
        signature = wallet.sign(self.signing_key, bytes.fromhex(cr_context.input_hash))
        merkle_sig = MerkleSignature.create(sig_hex=signature,
                                            timestamp=str(int(time.time())),
                                            sender=self.verifying_key)
        sbc = SubBlockContender.create_empty_sublock(input_hash=cr_context.input_hash,
                                                     sub_block_index=cr_context.sbb_idx, signature=merkle_sig,
                                                     prev_block_hash=StateDriver.get_latest_block_hash())
        # Send to block manager
        self.log.important2("Sending EMPTY SBC with input hash {} to block manager!".format(cr_context.input_hash))
        self._send_msg_over_ipc(sbc)

    def _create_sbc_from_batch(self, cr_context: CRContext):
        """
        Creates a Sub Block Contender from a TransactionBatch
        """
        import traceback
        self.log.info("Building sub block contender for input hash {}".format(cr_context.input_hash))

        try:
            sb_data = cr_context.get_subblock_rep()
            # self.log.important3("GOT SB DATA: {}".format(sb_data))

            txs_data = [TransactionData.create(contract_tx=d[0], status=d[1], state=d[2]) for d in sb_data]
            txs_data_serialized = [TransactionData.create(contract_tx=d[0], status=d[1], state=d[2]).serialize() for d in sb_data]
            txs = [d[0] for d in sb_data]

            # build sbc
            merkle = MerkleTree.from_raw_transactions(txs_data_serialized)
            signature = wallet.sign(self.signing_key, merkle.root)
            merkle_sig = MerkleSignature.create(sig_hex=signature,
                                                timestamp=str(time.time()),
                                                sender=self.verifying_key)
            sbc = SubBlockContender.create(result_hash=merkle.root_as_hex, input_hash=cr_context.input_hash,
                                           merkle_leaves=merkle.leaves, sub_block_index=cr_context.sbb_idx,
                                           signature=merkle_sig, transactions=txs_data,
                                           prev_block_hash=StateDriver.get_latest_block_hash())

            # Send sbc to block manager
            self.log.important2("Sending SBC with {} txs and input hash {} to block manager!"
                                .format(len(txs), cr_context.input_hash))
            self._send_msg_over_ipc(sbc)
        except Exception as e:
            exp = traceback.format_exc()
            self.log.fatal("GOT EXP BUILDING SB: {}".format(e))
            self.log.error("GOT EXP BUILDING SB: {}".format(exp))
            raise e

    # raghu todo sb_index is not correct between sb-builder and seneca-client. Need to handle more than one sb per client?
    def _execute_next_sb(self, input_hash: str, tx_batch: TransactionBatch, sbb_idx: int):
        self.log.debug("SBB {} attempting to build {} block with sub block index {}"
                       .format(self.sbb_index, "empty sub" if tx_batch.is_empty else "sub", sbb_idx))

        if self.client.execute_sb(input_hash, tx_batch.transactions, self._create_empty_sbc \
                                     if tx_batch.is_empty else self._create_sbc_from_batch):
            self._next_block_to_make.state = NextBlockState.PROCESSED
            return True
        return False

    def _make_next_sb(self):
        if not self.move_next_block_to_make():
            self.log.debug("Not ready to make next sub-block. Waiting for seneca-client to be ready ... ")
            return

        # now start next one
        cur_block_index = self._next_block_to_make.next_block_index
        sb_index_start = cur_block_index * NUM_SB_PER_BLOCK_PER_BUILDER
        for i in range(NUM_SB_PER_BLOCK_PER_BUILDER):
            sb_idx = sb_index_start + i
            if sb_idx >= len(self.sb_managers):    # out of range already
                self.log.debug("Uneven sub-blocks per block. May not work seneca clients properly in current scheme")
                self.log.debug("i {} num_sb_pb_pb {} num_sb_mgrs {} sb_idx {}".format(i, NUM_SB_PER_BLOCK_PER_BUILDER, len(self.sb_managers), sb_idx))
                return

            if len(self.sb_managers[sb_idx].to_finalize_txs) > NUM_CACHES:
                self.sb_managers[sb_idx].to_finalize_txs.pop_front()
            if len(self.sb_managers[sb_idx].pending_txs) > 0:
                input_hash, txs_bag = self.sb_managers[sb_idx].pending_txs.pop_front()
                self.log.debug("Make next sub-block with input hash {}".format(input_hash))
                sbb_idx = self.sb_managers[sb_idx].sub_block_index
                if self._execute_next_sb(input_hash, txs_bag, sbb_idx) and self.sb_managers[sb_idx].num_pending_sb > 0:
                    self.sb_managers[sb_idx].num_pending_sb -= 1
            else:
                self.sb_managers[sb_idx].num_pending_sb += 1
                self.log.debug("No transaction bag available yet. Wait ...")
                # self.pending_block_index = self.cur_block_index

    def _make_next_sub_block(self):
        self.log.info("Merge pending db to master db")
        # for i in len(self.clients):
            # self.clients[i].update_master_db()

        # first commit current state only if we have some pending dbs!
        if not self.startup:
            self.client.update_master_db()
        else:
            self.startup = False

        self._make_next_sb()
