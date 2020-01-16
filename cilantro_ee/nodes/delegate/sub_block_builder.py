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


from typing import Dict, Callable
from cilantro_ee.services.storage.state import MetaDataStorage
from cilantro_ee.constants.zmq_filters import *
from cilantro_ee.constants.system_config import *
from cilantro_ee.constants.ports import MN_TX_PUB_PORT
from cilantro_ee.constants.block import INPUT_BAG_TIMEOUT

from cilantro_ee.core.containers.merkle_tree import MerkleTree
from cilantro_ee.core.containers.linked_hashtable import LinkedHashTable

from cilantro_ee.core.crypto.wallet import Wallet

from cilantro_ee.core.messages.message_type import MessageType
from cilantro_ee.core.messages.message import Message

from cilantro_ee.core.utils.block_sub_block_mapper import BlockSubBlockMapper
from cilantro_ee.core.utils.transaction import transaction_is_valid, TransactionException
from cilantro_ee.core.utils.worker import Worker

# we need to have our own constant that can override
from contracting.config import NUM_CACHES
from contracting.stdlib.bridge.time import Datetime
from contracting.db.cr.client import SubBlockClient
from contracting.db.cr.callback_data import SBData

from cilantro_ee.utils.hasher import Hasher
from cilantro_ee.core.crypto.wallet import _verify
from enum import Enum, unique
import asyncio, zmq.asyncio, time
from datetime import datetime
import hashlib
import logging
from decimal import Decimal

from cilantro_ee.core.nonces import NonceManager

class Payload:
    def __init__(self, sender, nonce, processor, stamps_supplied, contract_name, function_name, kwargs):
        self.sender = sender
        self.nonce = nonce
        self.processor = processor
        self.stampsSupplied = stamps_supplied
        self.contractName = contract_name
        self.functionName = function_name
        self.kwargs = kwargs


class UnpackedContractTransaction:
    def __init__(self, capnp_struct):
        kwargs = {}
        for entry in capnp_struct.payload.kwargs.entries:
            if entry.value.which() == 'fixedPoint':
                kwargs[entry.key] = Decimal(entry.value.fixedPoint)
            else:
                kwargs[entry.key] = getattr(entry.value, entry.value.which())

        self.payload = Payload(sender=capnp_struct.payload.sender,
                               nonce=capnp_struct.payload.nonce,
                               processor=capnp_struct.payload.processor,
                               stamps_supplied=capnp_struct.payload.stampsSupplied,
                               contract_name=capnp_struct.payload.contractName,
                               function_name=capnp_struct.payload.functionName,
                               kwargs=kwargs)



class SBClientManager:
    def __init__(self, sbb_idx, loop):
        # self.client = SubBlockClient(sbb_idx=sbb_idx, num_sbb=NUM_SB_PER_BLOCK, loop=loop)
        self.next_sm_index = 0
        self.max_caches = 2
        self.sb_caches = []


# This is a convenience struct to hold all data related to a sub-block in one place.
# Since we have more than one sub-block per process, SBB'er will hold an array of SBManager objects
class TransactionBag:
    def __init__(self, latest_timestamp: int=0):
        self.latest_timestamp = latest_timestamp
        self.pending_txs = LinkedHashTable()

    def get_empty_input_hash(self):
        return Hasher.hash(str(self.latest_timestamp), return_bytes=True)

    def make_empty_bag(self):
        self.latest_timestamp += 1
        ih = self.get_empty_input_hash()
        _, bag = Message.get_message_packed(
                         MessageType.TRANSACTION_BATCH, transactions=[],
                         timestamp=self.latest_timestamp, inputHash=ih)
        return ih, bag

    def empty_queue(self):
        return len(self.pending_txs) == 0

    def get_next_bag(self):
        if self.empty_queue():
            return self.make_empty_bag()
        return self.pending_txs.pop_front()

    def insert_front(self, input_hash, bag):
        self.pending_txs.insert_front(input_hash, bag)

    def add_bag(self, bag):
        timestamp = bag.timestamp

        if (timestamp <= self.latest_timestamp) or \
           bag.inputHash in self.pending_txs:
            return False

        self.latest_timestamp = timestamp
        self.pending_txs.append(bag.inputHash, bag)
        return True

    # returns the number of non-empty bags thrown away in the process
    def pop_to_align_bag(self, input_hash):
        num_non_empty_bags = 0
        if input_hash in self.pending_txs:
            ih, bag = self.pending_txs.pop_front()
            while input_hash != ih:
                if len(bag.transactions) > 0:
                    num_non_empty_bags += 1
                ih, bag = self.pending_txs.pop_front()
            # now top one in pending_txs is with input_hash
            # throw it away if is empty bag otherwise keep it
            if len(bag.transactions) > 0:
                self.pending_txs.insert_front(ih, bag)
        return num_non_empty_bags
          


class TxnBagManager:
    def __init__(self, num_txn_bag_queues: int, bag_sleep_interval: int=1,
                 bag_timeout: int=INPUT_BAG_TIMEOUT, verify_bag: bool=True):
        self.nonce_manager = NonceManager()
        self.num_txn_bag_queues = num_txn_bag_queues
        self.txn_bags = []
        for idx in range(num_txn_bag_queues):
            self.txn_bags.append(TransactionBag())
        self.bag_sleep_interval = bag_sleep_interval
        self.bag_timeout = bag_timeout
        self.verify_bag = verify_bag
        self.bags_in_process = LinkedHashTable()
        self.last_active_bag_idx = 0
        self.num_non_empty_txn_bags = 0

    def verify_transaction_bag(self, bag):
        # Set up a hasher for input hash and a list for valid txs
        h = hashlib.sha3_256()

        for tx in bag.transactions:
            # Double check to make sure all transactions are valid
            try:
                transaction_is_valid(tx=tx,
                                     expected_processor=bag.sender,
                                     driver=self.nonce_manager,
                                     strict=False)
            except TransactionException:
                return False

            # Hash all transactions regardless because the proof from
            #      masternodes is derived from all hashes
            h.update(tx.as_builder().to_bytes_packed())

        h.update('{}'.format(bag.timestamp).encode())
        input_hash = h.digest()
        if input_hash != bag.inputHash or \
           not _verify(bag.sender, h.digest(), bag.signature):
            return False

        return True

    def get_active_bag_idx(self):
        return self.last_active_bag_idx

    def record_bag_added(self, bag):
        if len(bag.transactions) > 0:
            self.num_non_empty_txn_bags += 1

    def record_bag_removed(self, bag):
        if len(bag.transactions) > 0:
            self.num_non_empty_txn_bags -= 1

    def reduce_non_empty_bag_count(self, count):
        self.num_non_empty_txn_bags -= count

    def get_non_empty_bag_count(self):
        return self.num_non_empty_txn_bags

    def reset_non_empty_bag_count(self):
        self.num_non_empty_txn_bags = 0

    def add_bag(self, idx, bag):
        if self.txn_bags[idx].add_bag(bag):
            self.record_bag_added(bag)

    def remove_top_bag(self):
        if len(self.bags_in_process) == 0:
            return
        # assert len(self.bags_in_process) >= 1, "screw up in TxnBagManager!!"
        input_hash, bag = self.bags_in_process.pop_front()
        self.record_bag_removed(bag)

    def previous_process_index(self):
        self.last_active_bag_idx -= 1
        if self.last_active_bag_idx < 0:
            self.last_active_bag_idx += self.num_txn_bag_queues

    def next_process_index(self):
        self.last_active_bag_idx += 1
        if self.last_active_bag_idx == self.num_txn_bag_queues:
            self.last_active_bag_idx = 0

    def push_bag_in_process(self, hash, bag):
        self.bags_in_process.append(hash, bag)
        self.next_process_index()

    def pop_bag_in_process(self):
        self.previous_process_index()
        return self.bags_in_process.pop_back()

    def return_bags_in_process(self):
        while len(self.bags_in_process) > 0:
            ih, bag = self.pop_bag_in_process()
            idx = self.get_active_bag_idx()
            self.txn_bags[idx].insert_front(ih, bag)

    def align_bags(self, num_builders, sb_numbers, input_hashes):
        self.return_bags_in_process()
        final_bag_idx = -1
        for sb_num, input_hash in zip(sb_numbers, input_hashes):
            bag_idx = BlockSubBlockMapper.get_bag_index(sb_num, num_builders)
            count = self.txn_bags[bag_idx].pop_to_align_bag(input_hash)
            self.reduce_non_empty_bag_count(count)
            if bag_idx > final_bag_idx:
                final_bag_idx = bag_idx
        if final_bag_idx >= 0:
            self.last_active_bag_idx = final_bag_idx

    async def get_next_bag(self):
        idx = self.get_active_bag_idx()

        # wait until a bag is available or timeout
        elapsed = 0
        while self.txn_bags[idx].empty_queue() and elapsed < self.bag_timeout:
            await asyncio.sleep(self.bag_sleep_interval)
            elapsed += self.bag_sleep_interval

        # now fetch the bag, verify if needed and return
        hash, bag = self.txn_bags[idx].get_next_bag()
        while self.verify_bag and not self.verify_transaction_bag(bag):
            hash, bag = self.txn_bags[idx].get_next_bag()
 
        self.push_bag_in_process(hash, bag)

        return hash, bag


    def commit_nonces(self):
        self.nonce_manager.commit_nonces()

    def discord_nonces(self):
        # Toss all pending nonces
        self.nonce_manager.delete_pending_nonces()

  

class SubBlockMaker:

    def __init__(self, wallet: Wallet, sbb_index: int, num_sb_builders: int, 
                 num_sub_blocks: int, log: logging.getLoggerClass(),
                 event_callbacks: dict, loop: asyncio.AbstractEventLoop):

        self.wallet = wallet
        self.sb_blder_idx = sbb_index
        self.num_sb_builders = num_sb_builders
        self.event_callbacks = event_callbacks
        self.log = log

        self.tb_mgr = TxnBagManager(num_sub_blocks)
        self.state = MetaDataStorage()
        self.client = SubBlockClient(sbb_idx=sbb_index, 
                                     num_sbb=num_sb_builders, loop=loop)


    def _create_empty_sbc(self, sb_num: int, sb_data: SBData):
        """
        Creates an Empty Sub Block Contender
        """

        # raghu todo - makes sure input_hash is consistently either str or bytes
        if type(sb_data.input_hash) == str:
            input_hash = bytes.fromhex(sb_data.input_hash)
        else:
            input_hash = sb_data.input_hash

        self.log.info("Building empty sub block contender for input hash {}"
                      .format(sb_data.input_hash.hex()))

        _, merkle_proof = Message.get_message_packed(
                                    MessageType.MERKLE_PROOF,
                                    hash=input_hash,
                                    signer=self.wallet.verifying_key(),
                                    signature=self.wallet.sign(input_hash))

        return Message.get_message_packed(MessageType.SUBBLOCK_CONTENDER,
                                   resultHash=input_hash,
                                   inputHash=input_hash,
                                   merkleLeaves=[],
                                   signature=merkle_proof,
                                   transactions=[],
                                   subBlockNum=sb_num,
                                   prevBlockHash=self.state.latest_block_hash)


    def _create_sbc_from_batch(self, sb_num: int, sb_data: SBData):

        """
        Creates a Sub Block Contender from a TransactionBatch
        """

        self.log.info("Building sub block contender for input hash {}".format(sb_data.input_hash))
        exec_data = sb_data.tx_data

        txs_data = []

        # Add stamps used to TransactionData payload
        for i in range(len(exec_data)):
            d = exec_data[i]
            # raghu todo - get txns from txn_mgr at top of the stack
            tx = self.pending_transactions[i]
            _, txn_msg = Message.get_message_packed(
                                    MessageType.TRANSACTION_DATA,
                                    transaction=tx,
                                    status=d.status,
                                    state=d.state)
            txs_data.append(txn_msg)

        # build sbc
        merkle = MerkleTree.from_raw_transactions(txs_data)

        _, merkle_proof = Message.get_message_packed(
                                    MessageType.MERKLE_PROOF,
                                    hash=merkle.root,
                                    signer=self.wallet.verifying_key(),
                                    signature=self.wallet.sign(merkle.root))

        return Message.get_message_packed(
                           MessageType.SUBBLOCK_CONTENDER,
                           resultHash=merkle.root,
                           inputHash=sb_data.input_hash,
                           merkleLeaves=[leaf for leaf in merkle.leaves],
                           signature=merkle_proof,
                           transactions=[tx for tx in txs_data],
                           subBlockNum=sb_num,
                           prevBlockHash=self.state.latest_block_hash)



    def create_sb_contender(self, sb_num: int, sb_data: SBData):
        if len(sb_data.tx_data) > 0:
            mtype, sbc = self._create_sbc_from_batch(sb_num, sb_data)
        else:
            mtype, sbc = self._create_empty_sbc(sb_num, sb_data)
        self.event_callbacks['sb_contender'](mtype, sbc)


    def execute_sb(self, input_hash: bytes, tx_batch: list,
                   timestamp: float, sb_num: int):

        callback = self.create_sb_contender

        # Pass protocol level variables into environment
        #    so they are accessible at runtime in smart contracts
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

        transactions = []
        for transaction in tx_batch:
            # This should be streamlined so that we can just pass the tx_batch
            # forward because it's already ready to be processed at this point.
            # The reason why it isn't like this already is because Contracting
            # uses a weird pseudo wrapper for the capnp struct

            transactions.append(UnpackedContractTransaction(transaction))

        result = self.client.execute_sb(input_hash, transactions, sb_num,
                                        callback, environment=environment)
        self.log.success(f"Result for TX batch: {result}")


    async def make_next_sb(self):
        # now start next one
        bag_idx = self.tb_mgr.get_active_bag_idx()
        input_hash, bag = await self.tb_mgr.get_next_bag(self)
        sb_num = BlockSubBlockMapper.get_sub_block_num(bag_idx, 
                                                       self.sb_blder_idx,
                                                       self.num_sb_builders)

        self.log.info(f"Make next SB {sb_num} with input hash {input_hash}")

        self.execute_sb(input_hash, bag.transactions, bag.timestamp, sb_num)


    def inform_if_work(self):
        ne_bag_count = self.tb_mgr.get_non_empty_bag_count()
        if ne_bag_count == 1:
            self.event_callbacks['pending_txns']()

    def add_bag(self, idx, bag):
        self.tb_mgr.add_bag(idx, bag)
        self.inform_if_work()

    def inform_if_no_work(self):
        ne_bag_count = self.tb_mgr.get_non_empty_bag_count()
        if ne_bag_count <= 0:
            self.event_callbacks['no_txns']()
            if ne_bag_count < 0:
                self.log.error(f"Non-empty bag count {ne_bag_count} is negative")
                self.tb_mgr.reset_non_empty_bag_count()

    def commit_cur_sb(self):
        self.log.info("Merge pending db to master db")
        self.client.update_master_db()
        if self.sb_blder_idx == 0:
            self.tb_mgr.commit_nonces()
        self.tb_mgr.remove_top_bag()
        self.inform_if_no_work()
        # todo at this point, it can still execute next sb optimistically

    def discord_and_align(self, sb_numbers, input_hashes):
        self.log.info(f"Discording bags with hashes {input_hashes}")
        # todo - we can salvage good sbs, but right now just flush all clients
        self.client.flush_all()
        if self.sb_blder_idx == 0:
            self.tb_mgr.discord_nonces()
        self.tb_mgr.align_bags(sb_numbers, input_hashes)
        self.inform_if_no_work()



class SubBlockBuilder(Worker):
    def __init__(self, signing_key: str, sbb_index: int, num_sb_builders: int, 
                 sub_list: list, ipc_ip: str, ipc_port: int,
                 sub_port: int=MN_TX_PUB_PORT):

        super().__init__(signing_key=signing_key, name="SubBlockBuilder_{}"
                                                        .format(sbb_index))

        self.sb_blder_idx = sbb_index
        self.num_sb_builders = num_sb_builders

        self.sub_list = sub_list
        self.sub_port = sub_port
        self.sub_sockets = []

        # DEBUG -- TODO DELETE
        self.log.important("num sbb per blk {}".format(num_sb_builders))
        # END DEBUG

        # Create DEALER socket to talk to the BlockManager process over IPC
        self.ipc_dealer = self.manager.create_socket(socket_type=zmq.DEALER,
                                                     name="SBB-IPC-Dealer[{}]"
                                                           .format(sbb_index),
                                                     secure=False)

        # identity and other common options can be part of create_socket api
        self.ipc_dealer.setsockopt(zmq.IDENTITY, str(sbb_index).encode())
        # connect or bind is a separate step
        self.ipc_dealer.connect(port=ipc_port, protocol='ipc', ip=ipc_ip)

        self.tasks.append(self.ipc_dealer.add_handler(handler_func=self.handle_ipc_msg))
        # Adding message_handler with dictionary of actions as a separate step - this api could change
        # self.tasks.append(self.ipc_dealer.add_message_handler(self.get_ipc_message_action_dict()))

        event_callbacks = {
                              'no_txns': self.send_no_transactions,
                              'pending_txns': self.send_pending_transactions,
                              'sb_contender': self.send_ipc_message
                          }
        self.sb_maker = SubBlockMaker(self.wallet, sbb_index, num_sb_builders,
                                      len(sub_list), self.log,
                                      event_callbacks, self.loop)

        # create sub sockets to listen to txn-batchers
        self._create_sub_sockets()
        self.tasks.append(self._connect_and_process())

        self.log.notice(f"sbb_index {sbb_index} num_sb_blders {num_sb_builders}")


        self.run()

    def run(self):
        self.log.notice("SBB {} starting...".format(self.sb_blder_idx))
        self.loop.run_until_complete(asyncio.gather(*self.tasks))

    def get_ipc_message_action_dict(self):
        return {
            MessageType.MAKE_NEXT_BLOCK: self.__make_next_sub_block,
            MessageType.BLOCK_NOTIFICATION: self.__fail_block
        }

    async def _connect_and_process(self):
        # first make sure, we have overlay server ready
        await self._wait_until_ready()
        await self._connect_sub_sockets()
        mtype, msg = Message.get_message_packed(MessageType.READY)
        await self.ipc_dealer.send_multipart([mtype, msg])


    # we can use single socket and use sender and filter to figure out which sub-block data
    # only problem is whether subscriptions can be done per individual connection or not
    def _create_sub_sockets(self):
        for idx, sub_tup in enumerate(self.sub_list):
            sock_name = f"SBB-Sub[{self.sb_blder_idx}]-{idx}"
            sub = self.manager.create_socket(socket_type=zmq.SUB,
                                             name=sock_name, secure=True)

            sub.setsockopt(zmq.SUBSCRIBE, sub_tup[1].encode())
            self.sub_sockets.append(sub)

            self.tasks.append(sub.add_handler(handler_func=self.handle_sub_msg, handler_key=idx))

    async def _connect_sub_sockets(self):
        for idx, sub_tup in enumerate(self.sub_list):
            self.sub_sockets[idx].connect(port=self.sub_port, vk=sub_tup[0])
            # ?? self.sb_managers[smi].connected_vk = vk


    def handle_ipc_msg(self, frames):
        self.log.info("SBB received an IPC message {}".format(frames))
        assert len(frames) == 2, "Expected 2 frames: (msg_type, msg_blob). Got {} instead.".format(frames)

        msg_type = frames[0]
        msg_blob = frames[1]

        msg_type, msg, sender, timestamp, is_verified = Message.unpack_message(msg_type, msg_blob)
        self.log.info("Got message type '{}' msg '{}' from block manager. "
                      .format(msg_type, msg))
        if not is_verified:
            self.log.error("Failed to verify the message of type {} from {} at {}. Ignoring it .."
                          .format(msg_type, sender, timestamp))
            return

        if msg_type == MessageType.MAKE_NEXT_SB:
            self.sb_maker.make_next_sb()
        elif msg_type == MessageType.COMMIT_CUR_SB:
            self.sb_maker.commit_cur_sb()
        elif msg_type == MessageType.DISCORD_AND_ALIGN:
            self.sb_maker.discord_and_align(msg)
        else:
            self.log.error(f"Got invalid message type '{msg_type}'.")

    # ONLY FOR TX BATCHES
    def handle_sub_msg(self, frames, index):
        msg_filter, msg_type, msg_blob = frames

        msg_type, msg, sender, timestamp, is_verified = \
                                    Message.unpack_message(msg_type, msg_blob)
        if not is_verified:
            self.log.error(f"Failed to verify the message of type {msg_type}"
                           f" from {sender.hex()} at {timestamp}. Ignoring it")
            return

        if msg_type == MessageType.TRANSACTION_BATCH:
            self.sb_maker.add_bag(index, msg)
        else:
            self.log.error(f"Received illegal message of type {msg_type}"
                           f" from {sender.hex()}. Ignoring it")

    def send_ipc_message(self, msg_type: bytes, msg: bytes):
        self.ipc_dealer.send_multipart([msg_type, msg])

    def send_no_transactions(self):
        msg_type, msg = Message.get_message_packed(MessageType.NO_TRANSACTIONS)
        self.send_ipc_message(msg_type, msg)

    def send_pending_transactions(self):
        mtype,msg = Message.get_message_packed(MessageType.PENDING_TRANSACTIONS)
        self.send_ipc_message(mtype, msg)
