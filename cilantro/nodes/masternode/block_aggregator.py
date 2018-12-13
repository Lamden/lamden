from cilantro.logger.base import get_logger
from cilantro.protocol.multiprocessing.worker import Worker
from cilantro.protocol.structures.merkle_tree import MerkleTree

from cilantro.storage.state import StateDriver
from cilantro.storage.vkbook import VKBook
from cilantro.nodes.catchup import CatchupManager
from cilantro.nodes.masternode.mn_api import StorageDriver
from cilantro.nodes.masternode.block_contender import BlockContender

from cilantro.constants.zmq_filters import *
from cilantro.constants.ports import MASTER_ROUTER_PORT, MASTER_PUB_PORT, DELEGATE_PUB_PORT, DELEGATE_ROUTER_PORT
from cilantro.constants.system_config import *

from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.consensus.sub_block_contender import SubBlockContender
from cilantro.messages.consensus.merkle_signature import MerkleSignature
from cilantro.messages.block_data.block_data import BlockData
from cilantro.messages.block_data.sub_block import SubBlock
from cilantro.messages.block_data.state_update import *
from cilantro.messages.block_data.block_metadata import NewBlockNotification
from cilantro.messages.transaction.data import TransactionData

from cilantro.utils.hasher import Hasher
from cilantro.protocol import wallet
from typing import List

import asyncio, zmq, os, time, itertools
from collections import defaultdict


class BlockAggregator(Worker):

    def __init__(self, ip, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = get_logger("BlockAggregator[{}]".format(self.verifying_key[:8]))
        self.ip = ip
        self.tasks = []

        self.result_hashes = {}
        self.sub_blocks = {}
        self.full_blocks = {}
        self.curr_block_hash = StorageDriver.get_latest_block_hash()

        self.pub, self.sub, self.router = None, None, None  # Set in build_task_list
        self.catchup_manager = None  # This gets set at the end of build_task_list once sockets are created
        self.is_catching_up = False

        self.run()

    def run(self):
        self.log.info("Block Aggregator starting...")
        self.build_task_list()

        # TODO put this back in when Catchup is implemented
        # self.log.notice("starting initial catchup...")
        # self.is_catching_up = True
        # self.catchup_manager.send_block_idx_req()

        self.loop.run_until_complete(asyncio.gather(*self.tasks))

    def build_task_list(self):
        self.sub = self.manager.create_socket(
            socket_type=zmq.SUB,
            name="BA-Sub-{}".format(self.verifying_key[-4:]),
            secure=True,
            # domain="sb-contender"
        )
        self.pub = self.manager.create_socket(
            socket_type=zmq.PUB,
            name="BA-Pub-{}".format(self.verifying_key[-4:]),
            secure=True,
            # domain="sb-contender"
        )
        self.pub.bind(ip=self.ip, port=MASTER_PUB_PORT)

        self.router = self.manager.create_socket(
            socket_type=zmq.ROUTER,
            name="BA-Router-{}".format(self.verifying_key[-4:]),
            secure=True,
            # domain="sb-contender"
        )
        self.router.setsockopt(zmq.ROUTER_MANDATORY, 1)  # FOR DEBUG ONLY
        self.router.setsockopt(zmq.IDENTITY, self.verifying_key.encode())
        self.router.bind(ip=self.ip, port=MASTER_ROUTER_PORT)

        self.tasks.append(self.sub.add_handler(self.handle_sub_msg))
        self.tasks.append(self.router.add_handler(self.handle_router_msg))

        # Listen to delegates for sub block contenders and state update requests
        self.sub.setsockopt(zmq.SUBSCRIBE, DEFAULT_FILTER.encode())
        for vk in VKBook.get_delegates():
            self.sub.connect(vk=vk, port=DELEGATE_PUB_PORT)
            self.router.connect(vk=vk, port=DELEGATE_ROUTER_PORT)

        # Listen to masters for new block notifs and state update requests from masters/delegates
        self.sub.setsockopt(zmq.SUBSCRIBE, CATCHUP_MN_DN_FILTER.encode())
        self.sub.setsockopt(zmq.SUBSCRIBE, DEFAULT_FILTER.encode())
        for vk in VKBook.get_masternodes():
            if vk != self.verifying_key:
                self.sub.connect(vk=vk, port=MASTER_PUB_PORT)
                self.router.connect(vk=vk, port=MASTER_ROUTER_PORT)

        self.catchup_manager = CatchupManager(verifying_key=self.verifying_key, pub_socket=self.pub,
                                              router_socket=self.router, store_full_blocks=True)

    def handle_sub_msg(self, frames):
        envelope = Envelope.from_bytes(frames[-1])
        msg = envelope.message

        if isinstance(msg, SubBlockContender):
            if self.is_catching_up:
                self.log.warning("Got SBC, but i'm still catching up. Ignoring: <{}>".format(msg))
                return
            else:
                self.recv_sub_block_contender(msg)

        elif isinstance(msg, NewBlockNotification):
            self.recv_new_block_notif(envelope.sender, msg)
            # TODO send this to the catchup manager

        elif isinstance(msg, BlockIndexRequest):
            self.catchup_manager.recv_block_idx_req(envelope.sender, msg)

        elif isinstance(msg, BlockIndexReply):
            self.catchup_manager.recv_block_idx_reply(envelope.sender, msg)

        elif isinstance(msg, BlockDataRequest):
            self.catchup_manager.recv_block_data_req(envelope.sender, msg)

        elif isinstance(msg, BlockDataReply):
            self.catchup_manager.recv_block_data_reply(msg)

        else:
            raise Exception("BlockAggregator got message type {} from SUB socket that it does not know how to handle"
                            .format(type(msg)))

    def handle_router_msg(self, frames):
        envelope = Envelope.from_bytes(frames[-1])
        msg = envelope.message

        if isinstance(msg, BlockIndexRequest):
            self.recv_state_update_request(id_frame=frames[0], req=msg)
        else:
            raise Exception("BlockAggregator got message type {} from ROUTER socket that it does not know how to handle"
                            .format(type(msg)))

    def recv_sub_block_contender(self, sbc: SubBlockContender):
        self.log.info("Received a sbc with result hash {} and input hash {}".format(sbc.result_hash, sbc.input_hash))
        assert not self.is_catching_up, "We should not be receiving SBCs when we are catching up!"

        # If the previous block hash is not in our index table, we could possibly be out of date, and should trigger
        # a catchup. NOTE -- we should probably get some consensus on these allegedly 'new' prev_block_hashes incase
        # a bad delegate decides to send us new bad SubBlockContenders and cause us to be in perpetual catchup
        if not StorageDriver.check_block_exists(sbc.prev_block_hash):
            self.log.warning("Masternode got SBC with prev block hash {} that does not exist in our index table! "
                             "Starting catchup\n(SBC={})".format(sbc.prev_block_hash, sbc))
            # TODO fix this to use tejas' new CatchupManager API
            self.catchup_manager.send_block_idx_req()
            self.is_catching_up = True
            return

        if self.result_hashes.get(sbc.result_hash):
            if self.result_hashes[sbc.result_hash].get('_consensus_reached_') or self.sub_blocks.get(sbc.result_hash):
                self.log.debugv('Already validated this SubBlock (result_hash={})'.format(
                    sbc.result_hash))
            elif self.check_sbc_already_verified(sbc):
                self.log.debugv('Already received and verified this SubBlockContender (result_hash={}, input_hash={})'
                                .format(sbc.result_hash, sbc.input_hash))
            else:
                if self.verify_sbc(sbc):
                    self.log.info('Received SubBlockContender for an existing result hash (result_hash={}, '
                                  'input_hash={})'.format(sbc.result_hash, sbc.input_hash))
                    self.aggregate_sub_block(sbc)
                else:
                    self.log.warning('Not a valid SubBlockContender for existing result hash (result_hash={}, '
                                     'input_hash={})'.format(sbc.result_hash, sbc.input_hash))
        else:
            if self.verify_sbc(sbc):
                self.log.info('Received SubBlockContender for a new result hash (result_hash={}, input_hash={})'
                              .format(sbc.result_hash, sbc.input_hash))
                self.aggregate_sub_block(sbc)
            else:
                self.log.warning('Not a valid SubBlockContender for new result hash (result_hash={}, input_hash={})'
                                 .format(sbc.result_hash, sbc.input_hash))

    def check_sbc_already_verified(self, sbc: SubBlockContender) -> bool:
        return sbc.signature.signature in self.result_hashes.get(sbc.result_hash, {}).get('_valid_signatures_')

    def verify_sbc(self, sbc: SubBlockContender) -> bool:
        # Validate signature
        if not sbc.signature.verify(bytes.fromhex(sbc.result_hash)):
            self.log.warning('This SubBlockContender does not have a valid signature! SBC: {}'.format(sbc))
            return False

        # Validate sbc prev block hash matches our current block hash
        if sbc.prev_block_hash != self.curr_block_hash:
            self.log.warning("SBC prev block hash {} does not match our current block hash {}! SBC: {}"
                             .format(sbc.prev_block_hash, self.curr_block_hash, sbc))
            return False

        # Validate merkle leaves
        if len(sbc.merkle_leaves) > 0:
            self.log.spam("This SubBlockContender have {} num of merkle leaves!".format(len(sbc.merkle_leaves)))
            if MerkleTree.verify_tree_from_str(sbc.merkle_leaves, root=sbc.result_hash) and self.validate_txs(sbc):
                self.log.spam('This SubBlockContender is valid!')
            else:
                self.log.warning('Could not verify Merkle tree for SBC {}'.format(sbc))
                return False

        return True

    def validate_txs(self, sbc: SubBlockContender) -> bool:
        for tx in sbc.transactions:
            if tx.hash not in sbc.merkle_leaves:
                self.log.warning('Received malicious txs that does not match merkle leaves! SBC: {}'.format(sbc))
                return False

        return True

    def aggregate_sub_block(self, sbc: SubBlockContender):
        # if not self.result_hashes.get(sbc.result_hash):
        if sbc.result_hash not in self.result_hashes:
            self.log.critical("CREATING DATA FOR RESULT HASH {}".format(sbc.result_hash))  # TODO remove
            self.result_hashes[sbc.result_hash] = {
                '_committed_': False,
                '_consensus_reached_': False,
                '_transactions_': {},
                '_valid_signatures_': {},
                '_input_hash_': sbc.input_hash,
                '_merkle_leaves_': sbc.merkle_leaves,
                '_sb_index_': sbc.sb_index,
                '_lastest_valid_': time.time()
            }

        self.log.info("Adding signature {} to sub-block result_hashes from sender {}".format(sbc.signature.signature,
                                                                                             sbc.signature.sender))
        self.result_hashes[sbc.result_hash]['_valid_signatures_'][sbc.signature.signature] = sbc.signature

        for tx in sbc.transactions:
            self.result_hashes[sbc.result_hash]['_transactions_'][tx.hash] = tx

        # DEBUG -- TODO DELETE
        self.log.important3("Delegate majroity: {}".format(DELEGATE_MAJORITY))
        self.log.important3("result hash {} has sigs {}".format(sbc.result_hash, self.result_hashes[sbc.result_hash]['_valid_signatures_']))
        # END DEBUG

        if len(self.result_hashes[sbc.result_hash]['_valid_signatures_']) >= DELEGATE_MAJORITY \
            and len(self.result_hashes[sbc.result_hash]['_transactions_']) == \
                len(self.result_hashes[sbc.result_hash]['_merkle_leaves_']):
            self.log.info('SubBlock is validated and consensus reached (result_hash={})'.format(sbc.result_hash))
            self.result_hashes[sbc.result_hash]['_consensus_reached_'] = True
            self.store_full_block()
        else:
            self.log.info('Saved valid sub block into memory (result_hash={}, signatures:{}/{}, transactions:{}/{})'.format(
                sbc.result_hash,
                len(self.result_hashes[sbc.result_hash]['_valid_signatures_']), DELEGATE_MAJORITY,
                len(self.result_hashes[sbc.result_hash]['_transactions_']),
                len(self.result_hashes[sbc.result_hash]['_merkle_leaves_'])
            ))
        self.cleanup_block_memory()

    def cleanup_block_memory(self):
        pass
        # TODO -- fix this!
        # self.result_hashes = {
        #     result_hash: self.result_hashes[result_hash] \
        #     for result_hash in self.result_hashes \
        #     if self.result_hashes[result_hash]['_lastest_valid_'] <= time.time() - SUB_BLOCK_VALID_PERIOD and
        #        self.result_hashes[result_hash].get('_committed_')
        # }

    def store_full_block(self):
        sub_blocks = {
            result_hash: self.result_hashes[result_hash] for result_hash in self.result_hashes
                if self.result_hashes[result_hash]['_consensus_reached_']
                and not self.result_hashes[result_hash]['_committed_']
        }

        if len(sub_blocks) < NUM_SB_PER_BLOCK:
            self.log.info('Received {}/{} required sub-blocks so far.'.format(len(sub_blocks), NUM_SB_PER_BLOCK))
            return

        # Sort the merkle roots
        unordered_merkle_roots = [result_hash for result_hash in sub_blocks]
        merkle_roots = sorted(unordered_merkle_roots, key=lambda result_hash: self.result_hashes[result_hash]['_sb_index_'])

        # Build the sub-blocks
        sb_data = []
        for root in merkle_roots:
            data = self.result_hashes[root]
            sigs = data['_valid_signatures_'].values()
            # TODO change sub-block contender to pass around TransactionData struct instead of binary payloads
            # or change sub-block to store binary payloads instead of structs
            txs = [data['_transactions_'][tx_hash] for tx_hash in data['_merkle_leaves_']]
            sb = SubBlock.create(merkle_root=root, signatures=sigs, merkle_leaves=data['_merkle_leaves_'],
                                 sub_block_idx=data['_sb_index_'], input_hash=data['_input_hash_'], transactions=txs)
            sb_data.append(sb)

        assert len(sb_data) == NUM_SB_PER_BLOCK, "Aggregator has {} sub blocks but there are {} SBs/per/block" \
                                                 .format(len(sb_data), NUM_SB_PER_BLOCK)

        # TODO wrap storage in try/catch. Add logic for storage failure

        block_data = StorageDriver.store_block(sb_data)
        assert block_data.prev_block_hash == self.curr_block_hash, "Current block hash {} does not match StorageDriver previous " \
                                                        "block hash {}".format(self.curr_block_hash, block_data.prev_block_hash)

        self.curr_block_hash = block_data.block_hash
        StateDriver.update_with_block(block_data)
        self.log.success("STORED BLOCK WITH HASH {}".format(block_data.block_hash))
        self.send_new_block_notification(block_data)
        for result_hash in merkle_roots:
            self.sub_blocks[result_hash] = True
            self.result_hashes[result_hash]['_committed_'] = True

    def send_new_block_notification(self, block_data: BlockData):
        new_block_notif = NewBlockNotification.create_from_block_data(block_data)
        self.pub.send_msg(msg=new_block_notif, header=DEFAULT_FILTER.encode())
        block_hash = block_data.block_hash
        self.log.info('Published new block notif with hash "{}"'.format(block_hash))

        if self.full_blocks.get(block_hash):
            self.log.info('Already received block hash "{}", adding to consensus count.'.format(block_hash))
            self.full_blocks[block_hash]['_count_'] += 1

        else:

            self.log.info('Created resultant block-hash "{}"'.format(block_hash))
            self.full_blocks[block_hash] = {
                '_block_metadata_': new_block_notif,
                '_consensus_reached_': False,
                '_senders_': {self.verifying_key},
            }

        # return new_block_notif

    def recv_new_block_notif(self, sender_vk: str, nbc: NewBlockNotification):
        block_hash = nbc.block_hash

        if not self.full_blocks.get(block_hash):
            self.log.info('Received NEW block hash "{}", did not yet receive valid sub blocks from delegates.'.format(block_hash))
            self.full_blocks[block_hash] = {
                '_block_metadata_': nbc,
                '_consensus_reached_': False,
                '_senders_': {sender_vk}
            }

        if not self.full_blocks[block_hash]['consensus_reached']:
            self.log.info('Received notification for KNOWN block hash "{}", adding to consensus count.'.format(block_hash))
            self.full_blocks[block_hash]['_senders_'].add(sender_vk)
            if len(self.full_blocks[block_hash]['_senders_']) >= MASTERNODE_MAJORITY:
                self.full_blocks[block_hash]['_consensus_reached_'] = True
                # TODO consensus on new block notif reached here. Do whatever.

        else:
            self.log.info('Received notification for KNOWN block hash "{}" but consensus already reached.'.format(block_hash))

    def recv_state_update_request(self, id_frame: bytes, req: BlockIndexRequest):
        blocks = StorageDriver.get_latest_blocks(req.block_hash)
        reply = BlockDataReply.create(blocks)
        self.router.send_multipart([])
