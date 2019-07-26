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

from cilantro_ee.logger import get_logger
from cilantro_ee.storage.state import MetaDataStorage
from cilantro_ee.constants.zmq_filters import *
from cilantro_ee.constants.system_config import *

from cilantro_ee.messages.base.base import MessageBase
from cilantro_ee.messages.envelope.envelope import Envelope
# from cilantro_ee.messages.block_data.state_update import *
from cilantro_ee.messages.block_data.notification import FailedBlockNotification
from cilantro_ee.messages.consensus.merkle_signature import MerkleSignature
from cilantro_ee.messages.consensus.sub_block_contender import SubBlockContender
from cilantro_ee.messages.consensus.align_input_hash import AlignInputHash
from cilantro_ee.messages.transaction.batch import TransactionBatch
from cilantro_ee.messages.transaction.data import TransactionData, TransactionDataBuilder
from cilantro_ee.messages.signals.node import Ready
from cilantro_ee.messages._new.message import MessageTypes, MessageManager
from contracting.config import NUM_CACHES
from contracting.stdlib.bridge.time import Datetime
from contracting.db.cr.client import SubBlockClient
from contracting.db.cr.callback_data import ExecutionData, SBData

from cilantro_ee.protocol import wallet
from cilantro_ee.protocol.multiprocessing.worker import Worker
from cilantro_ee.protocol.utils.network_topology import NetworkTopology

from cilantro_ee.protocol.structures.merkle_tree import MerkleTree
from cilantro_ee.protocol.structures.linked_hashtable import LinkedHashTable

from cilantro_ee.utils.hasher import Hasher
from cilantro_ee.utils.utils import int_to_bytes, bytes_to_int

from enum import Enum, unique
import asyncio, zmq.asyncio, time, os
from datetime import datetime
from typing import List

from cilantro_ee.messages import capnp as schemas
import os
import capnp

blockdata_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/blockdata.capnp')
subblock_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/subblock.capnp')
envelope_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/envelope.capnp')
transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')
signal_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/signals.capnp')

@unique
class NextBlockState(Enum):
    NOT_READY = 0
    READY = 1
    PROCESSED = 2


# raghu
class SBClientManager:
    def __init__(self, sbb_idx, loop):
        # self.client = SubBlockClient(sbb_idx=sbb_idx, num_sbb=NUM_SB_PER_BLOCK, loop=loop)
        self.next_sm_index = 0
        self.max_caches = 2
        self.sb_caches = []


class NextBlockToMake:
    def __init__(self, block_index: int=0, state: NextBlockState=NextBlockState.READY):
        self.next_block_index = block_index
        self.state = state


# This is a convenience struct to hold all data related to a sub-block in one place.
# Since we have more than one sub-block per process, SBB'er will hold an array of SubBlockManager objects
class SubBlockManager:
    def __init__(self, sub_block_index: int, sub_socket, processed_txs_timestamp: int=0):
        self.sub_block_index = sub_block_index
        self.connected_vk = None
        self.empty_input_iter = 0
        self.sub_socket = sub_socket
        self.processed_txs_timestamp = processed_txs_timestamp
        self.pending_txs = LinkedHashTable()
        self.to_finalize_txs = LinkedHashTable()

    def get_empty_input_hash(self):
        self.empty_input_iter += 1
        return Hasher.hash(self.connected_vk + str(self.empty_input_iter))


class SubBlockBuilder(Worker):
    def __init__(self, ip: str, signing_key: str, ipc_ip: str, ipc_port: int, sbb_index: int, *args, **kwargs):
        super().__init__(signing_key=signing_key, name="SubBlockBuilder_{}".format(sbb_index))

        self.state = MetaDataStorage()

        self.ip = ip
        self.sb_blder_idx = sbb_index
        self.startup = True
        self.num_txn_bags = 0
        self._empty_txn_batch = TransactionBatch.create([])

        self.client = SubBlockClient(sbb_idx=sbb_index, num_sbb=NUM_SB_PER_BLOCK, loop=self.loop)

        # DEBUG -- TODO DELETE
        self.log.important("num sbb per blk {}".format(NUM_SB_PER_BLOCK))
        # END DEBUG

        # Create DEALER socket to talk to the BlockManager process over IPC
        self.ipc_dealer = None
        self._create_dealer_ipc(port=ipc_port, ip=ipc_ip, identity=str(self.sb_blder_idx).encode())

        # BIND sub sockets to listen to witnesses
        self.sb_managers = []
        self._create_sub_sockets()
        # need to tie with catchup state to initialize to real next_block_to_make
        self._next_block_to_make = NextBlockToMake()
        self.tasks.append(self._connect_and_process())

        self.log.notice("sbb_index {} tot_sbs {} num_blks {} num_sb_blders {} num_sb_per_block {} num_sb_per_builder {} sbs_per_blk_per_blder {}"
                        .format(sbb_index, NUM_SUB_BLOCKS, NUM_BLOCKS, NUM_SB_BUILDERS, NUM_SB_PER_BLOCK, NUM_SB_PER_BUILDER, NUM_SB_PER_BLOCK_PER_BUILDER))

        self.run()

    def run(self):
        self.log.notice("SBB {} starting...".format(self.sb_blder_idx))
        self.loop.run_until_complete(asyncio.gather(*self.tasks))

    async def _connect_and_process(self):
        # first make sure, we have overlay server ready
        await self._wait_until_ready()
        await self._connect_sub_sockets()
        await self.send_ready_to_bm()

    async def send_ready_to_bm(self):
        message = MessageManager.pack_dict(MessageTypes.READY_INTERNAL, arg_dict={'messageType': MessageTypes.READY_INTERNAL})
        self.ipc_dealer.send_multipart([int_to_bytes(MessageTypes.READY_INTERNAL), message])

    # raghu todo - call this right after catch up phase, need to figure out the right input hashes though for next block
    def initialize_next_block_to_make(self, next_block_index: int):
        self._next_block_to_make.next_block_index = next_block_index % NUM_BLOCKS
        self._next_block_to_make.state = NextBlockState.READY

    def move_next_block_to_make(self):
        if self._next_block_to_make.state == NextBlockState.PROCESSED:
            self.initialize_next_block_to_make(self._next_block_to_make.next_block_index + 1)

        return self._next_block_to_make.state == NextBlockState.READY

    def _create_dealer_ipc(self, port: int, ip: str, identity: bytes):
        self.log.info("Connecting to BlockManager's ROUTER socket with a DEALER using ip {}, port {}, and id {}"
                      .format(ip, port, identity))
        self.ipc_dealer = self.manager.create_socket(socket_type=zmq.DEALER, name="SBB-IPC-Dealer[{}]".format(self.sb_blder_idx), secure=False)
        self.ipc_dealer.setsockopt(zmq.IDENTITY, identity)
        self.ipc_dealer.connect(port=port, protocol='ipc', ip=ip)

        self.tasks.append(self.ipc_dealer.add_handler(handler_func=self.handle_ipc_msg))

    def _create_sub_sockets(self):
        for idx in range(NUM_SB_PER_BUILDER):
            sub = self.manager.create_socket(socket_type=zmq.SUB, name="SBB-Sub[{}]-{}".format(self.sb_blder_idx, idx),
                                             secure=True)

            sub.setsockopt(zmq.SUBSCRIBE, TRANSACTION_FILTER.encode())
            sb_index = idx * NUM_SB_BUILDERS + self.sb_blder_idx

            self.sb_managers.append(SubBlockManager(sub_block_index=sb_index, sub_socket=sub))
            self.tasks.append(sub.add_handler(handler_func=self.handle_sub_msg, handler_key=idx))

    async def _connect_sub_sockets(self):
        for smi, d in enumerate(NetworkTopology.get_sbb_publishers(self.verifying_key, self.sb_blder_idx), 0):
            vk, port, sb_idx = d['vk'], d['port'], d['sb_idx']
            assert self.sb_managers[smi].sub_block_index == sb_idx, "something went wrong in connections"
            self.sb_managers[smi].sub_socket.connect(port=port, vk=vk)
            self.sb_managers[smi].connected_vk = vk

    def _align_to_hash(self, smi, input_hash):
        num_discards = 0

        if input_hash in self.sb_managers[smi].pending_txs:
            # clear entirely to_finalize
            num_discards = num_discards + len(self.sb_managers[smi].to_finalize_txs)
            self.sb_managers[smi].to_finalize_txs.clear()
            ih2 = None
            while input_hash != ih2:
                ih2, txs_bag = self.sb_managers[smi].pending_txs.pop_front()
                self.adjust_work_load(txs_bag, False)
                num_discards = num_discards + 1
        elif input_hash in self.sb_managers[smi].to_finalize_txs:
            ih2 = None
            while input_hash != ih2:
                ih2, txs_bag = self.sb_managers[smi].to_finalize_txs.pop_front()
                num_discards = num_discards + 1
        return num_discards

    def align_input_hashes(self, aih: AlignInputHash):
        self.log.notice("Discarding all pending sub blocks and aligning input hash to {}".format(aih.input_hash))
        self.client.flush_all()
        self.startup = True
        # is this remainder or division here ??
        smi = aih.sb_index // NUM_SB_BUILDERS
        num_discards = self._align_to_hash(smi, aih.input_hash)
        self.log.debug("Discarded {} input bags to get alignment".format(num_discards))
        # at this point, any bags in to_finalize_txs should go back to the front of pending_txs
        while len(self.sb_managers[smi].to_finalize_txs) > 0:
            ih, txs_bag = self.sb_managers[smi].to_finalize_txs.pop_front()
            self.adjust_work_load(txs_bag, True)
            self.sb_managers[smi].pending_txs.insert_front(ih, txs_bag)
        # self._make_next_sb()

    def _fail_block(self, fbn: FailedBlockNotification):
        self.log.notice("FailedBlockNotification - aligning input hashes")

        num_discards = 0
        input_hashes = fbn.input_hashes[self.sb_blder_idx]
        smi = (fbn.first_sb_index + self.sb_blder_idx) // NUM_SB_BUILDERS

        for input_hash in input_hashes:
            num_discards = num_discards + self._align_to_hash(smi, input_hash)

        self.log.debug("Thrown away {} input bags to get alignment".format(num_discards))

        # at this point, any bags in to_finalize_txs should go back to the front of pending_txs
        while len(self.sb_managers[smi].to_finalize_txs) > 0:
            ih, txs_bag = self.sb_managers[smi].to_finalize_txs.pop_front()
            self.adjust_work_load(txs_bag, True)
            self.sb_managers[smi].pending_txs.insert_front(ih, txs_bag)

        self.client.flush_all()
        self.startup = True
        # self._make_next_sb()

    def handle_ipc_msg(self, frames):
        self.log.info("SBB received an IPC message {}".format(frames))
        assert len(frames) == 2, "Expected 2 frames: (msg_type, msg_blob). Got {} instead.".format(frames)

        msg_type = bytes_to_int(frames[0])
        msg_blob = frames[1]
        msg = None

        if msg_type == MessageTypes.MAKE_NEXT_BLOCK:
            self.log.success("MAKE NEXT BLOCK SIGNAL")
            self._make_next_sub_block()
            return

        if MessageBase.registry.get(msg_type) is not None:
            msg = MessageBase.registry[msg_type].from_bytes(msg_blob)

        if isinstance(msg, MessageBase):
            # DATA
            # if not matched consensus, then discard current state and use catchup flow
            if isinstance(msg, AlignInputHash):
                self.align_input_hashes(msg)

            # SIGNAL
            elif isinstance(msg, FailedBlockNotification):
                self._fail_block(msg)

            else:
                raise Exception("SBB got message type {} from IPC dealer socket that it does not know how to handle"
                                .format(type(msg)))

    def _send_msg_over_ipc(self, message):
        """
        Convenience method to send a MessageBase instance over IPC dealer socket. Includes a frame to identify the
        type of message
        """
        if isinstance(message, MessageBase):
            message_type = MessageBase.registry[type(message)]  # this is an int (enum) denoting the class of message

            self.ipc_dealer.send_multipart([int_to_bytes(message_type), message.serialize()])

    def adjust_work_load(self, input_bag: Envelope, is_add: bool):
        if input_bag.message.is_empty:
            self.log.info('Empty bag. Tossing.')
            return

        self.num_txn_bags += 1 if is_add else -1

        # Create Signal
        if self.num_txn_bags == 0:
            no_transactions = MessageManager.pack_dict(MessageTypes.NO_TRANSACTIONS,
                                                       arg_dict={'messageType': MessageTypes.NO_TRANSACTIONS})

            self.ipc_dealer.send_multipart([int_to_bytes(MessageTypes.NO_TRANSACTIONS), no_transactions])

        elif self.num_txn_bags == 1:
            # SIGNAL CREATION
            pending_transactions = MessageManager.pack_dict(MessageTypes.PENDING_TRANSACTIONS,
                                                            arg_dict={'messageType': MessageTypes.PENDING_TRANSACTIONS})

            self.ipc_dealer.send_multipart([int_to_bytes(MessageTypes.PENDING_TRANSACTIONS), pending_transactions])

    def handle_sub_msg(self, frames, index):
        # self.log.spam("Sub socket got frames {} with handler_index {}".format(frames, index))
        assert 0 <= index < len(self.sb_managers), "Got index {} out of range of sb_managers array {}".format(
            index, self.sb_managers)

        self.log.info('Got index {} with frames {}'.format(index, frames))

        envelope = Envelope.from_bytes(frames[-1])
        timestamp = envelope.meta.timestamp

        assert isinstance(envelope.message, TransactionBatch),\
            "Handler expected TransactionBatch but got {}".format(envelope.messages)

        if timestamp <= self.sb_managers[index].processed_txs_timestamp:
            self.log.debug("Got timestamp {} that is prior to the most recent timestamp {} for sb_manager {} tho"
                           .format(timestamp, self.sb_managers[index].processed_txs_timestamp, index))
            return

        input_hash = Hasher.hash(envelope)
        self.log.info(input_hash)
        # if the sb_manager already has this bag, ignore it
        if input_hash in self.sb_managers[index].pending_txs:
            self.log.debugv("Input hash {} already found in sb_manager at index {}".format(input_hash, index))
            return

        if not envelope.verify_seal():
            self.log.error("Could not validate seal for envelope {}".format(envelope))
            return

        # DEBUG -- TODO DELETE
        self.log.notice("Recv tx batch w/ {} transactions, and input hash {}".format(len(envelope.message.transactions), input_hash))


        # END DEBUG
        self.log.info(timestamp)
        self.sb_managers[index].processed_txs_timestamp = timestamp

        self.log.info("Queueing transaction batch for sb manager {}. SB_Manager={}".format(index, self.sb_managers[index]))
        self.adjust_work_load(envelope, True)

        self.sb_managers[index].pending_txs.append(input_hash, envelope)

    def _create_empty_sbc(self, sb_data: SBData):

        self.log.info("Building empty sub block contender for input hash {}".format(sb_data.input_hash))

        signature = self.wallet.sign(bytes.fromhex(sb_data.input_hash))

        merkle_proof = subblock_capnp.MerkleProof.new_message(**{
            'hash': bytes.fromhex(sb_data.input_hash),
            'signer': self.wallet.verifying_key(),
            'signature': signature
        }).to_bytes_packed()

        sbc = subblock_capnp.SubBlockContender.new_message(**{
              'resultHash': bytes.fromhex(sb_data.input_hash),
              'inputHash': bytes.fromhex(sb_data.input_hash),
              'merkleLeaves': [],
              'signature': merkle_proof,
              'transactions': [],
              'subBlockIdx': self.sb_blder_idx,
              'prevBlockHash': self.state.get_latest_block_hash()
        }).to_bytes_packed()

        self.log.important2("Sending EMPTY SBC with input hash {} to block manager!".format(sb_data.input_hash))

        self.ipc_dealer.send_multipart([int_to_bytes(MessageTypes.SUBBLOCK_CONTENDER), sbc])

    def _create_sbc_from_batch(self, sb_data: SBData):
        """
        Creates a Sub Block Contender from a TransactionBatch
        """

        self.log.info("Building sub block contender for input hash {}".format(sb_data.input_hash))

        exec_data = sb_data.tx_data

        txs_data = [transaction_capnp.TransactionData.new_message(**{
            'transaction': d.contract.serialize(),
            'status': str(d.status),
            'state': d.state,
            'contractType': 0 # To be deprecated
        }).to_bytes_packed() for d in exec_data]

        txs = [d.contract for d in exec_data]

        # build sbc
        merkle = MerkleTree.from_raw_transactions(txs_data)

        merkle_proof = subblock_capnp.MerkleProof.new_message(**{
            'hash': merkle.root,
            'signer': self.wallet.verifying_key(),
            'signature': self.wallet.sign(merkle.root)
        }).to_bytes_packed()

        sbc = subblock_capnp.SubBlockContender.new_message(**{
            'resultHash': merkle.root,
            'inputHash': bytes.fromhex(sb_data.input_hash),
            'merkleLeaves': [leaf for leaf in merkle.leaves],
            'signature': merkle_proof,
            'transactions': [tx for tx in txs_data],
            'subBlockIdx': self.sb_blder_idx,
            'prevBlockHash': self.state.get_latest_block_hash()
        }).to_bytes_packed()

        self.log.important2("Sending SBC with {} txs and input hash {} to block manager!"
                            .format(len(txs), sb_data.input_hash))

        self.ipc_dealer.send_multipart([int_to_bytes(MessageTypes.SUBBLOCK_CONTENDER), sbc])


    def create_sb_contender(self, sb_data: SBData):
        self.log.info('SBData returned: {}'.format(sb_data.tx_data))
        if len(sb_data.tx_data) > 0:
            self._create_sbc_from_batch(sb_data)
        else:
            self._create_empty_sbc(sb_data)


    # raghu todo sb_index is not correct between sb-builder and seneca-client. Need to handle more than one sb per client?
    def _execute_sb(self,
                    input_hash: str,
                    tx_batch: TransactionBatch,
                    timestamp: float,
                    sbb_idx: int):

        self.log.info("SBB {} attempting to build a sub block with index {}"
                       .format(self.sb_blder_idx, sbb_idx))

        # callback = self._create_empty_sbc if tx_batch.is_empty else self._create_sbc_from_batch
        callback = self.create_sb_contender

        # Pass protocol level variables into environment so they are accessible at runtime in smart contracts
        block_hash = self.state.latest_block_hash
        block_num = self.state.latest_block_num

        dt = datetime.utcfromtimestamp(timestamp)
        dt_object = Datetime(year=dt.year,
                             month=dt.month,
                             day=dt.day,
                             hour=dt.hour,
                             minute=dt.minute,
                             second=dt.second,
                             microsecond=dt.microsecond)

        environment = {
            'block_hash': block_hash,
            'block_num': block_num,
            'now': dt_object
        }

        self.log.info('Transactions to execute: {}'.format(tx_batch.ordered_transactions))

        result = self.client.execute_sb(input_hash,
                                        tx_batch.ordered_transactions,
                                        callback,
                                        environment=environment)

        self.log.success('RESULT FOR TX BATCH: {}'.format(result))

        if result:
            self._next_block_to_make.state = NextBlockState.PROCESSED
            return True
        return False

    def _execute_input_bag(self, input_hash: str, envelope: Envelope, sbb_idx: int):
        return self._execute_sb(input_hash, envelope.message, envelope.meta.timestamp, sbb_idx)

    def _make_next_sb(self):
        if not self.move_next_block_to_make():
            self.log.info("Not ready to make next sub-block. Waiting for seneca-client to be ready ... ")
            return

        # now start next one
        cur_block_index = self._next_block_to_make.next_block_index
        self.log.info('Working on {}'.format(cur_block_index))

        sm_idx_start = cur_block_index * NUM_SB_PER_BLOCK_PER_BUILDER

        for i in range(NUM_SB_PER_BLOCK_PER_BUILDER):
            sm_idx = sm_idx_start + i

            if sm_idx >= len(self.sb_managers):    # out of range already
                self.log.info("Uneven sub-blocks per block. May not work seneca clients properly in current scheme")
                self.log.info("i {} num_sb_pb_pb {} num_sb_mgrs {} sm_idx {}".format(i, NUM_SB_PER_BLOCK_PER_BUILDER, len(self.sb_managers), sm_idx))
                return

            if len(self.sb_managers[sm_idx].to_finalize_txs) > NUM_CACHES:
                self.sb_managers[sm_idx].to_finalize_txs.pop_front()

            sb_index = self.sb_managers[sm_idx].sub_block_index
            if len(self.sb_managers[sm_idx].pending_txs) > 0:

                input_hash, envelope = self.sb_managers[sm_idx].pending_txs.pop_front()
                self.adjust_work_load(envelope, False)
                self.log.info("Make next sub-block with input hash {}".format(input_hash))
                self.sb_managers[sm_idx].to_finalize_txs.append(input_hash, envelope)
                self._execute_input_bag(input_hash, envelope, sb_index)
                self.log.success('EXEC')

            else:
                timestamp = float(time.time())
                input_hash = self.sb_managers[sm_idx].get_empty_input_hash()
                self._execute_sb(input_hash, self._empty_txn_batch, timestamp, sb_index)
                self.log.success('EXEC')

    def _make_next_sub_block(self):
        if not self.startup:
            self.log.info("Merge pending db to master db")
            self.client.update_master_db()
        else:
            self.startup = False
            time.sleep(2)

        self._make_next_sb()
