from cilantro.logger.base import get_logger
from cilantro.protocol.multiprocessing.worker import Worker
from cilantro.protocol.structures.merkle_tree import MerkleTree

from cilantro.storage.db import VKBook
from cilantro.storage.driver import StorageDriver

from cilantro.constants.zmq_filters import MASTERNODE_DELEGATE_FILTER, MASTER_MASTER_FILTER, DEFAULT_FILTER
from cilantro.constants.ports import MASTER_ROUTER_PORT, MASTER_PUB_PORT, DELEGATE_PUB_PORT, DELEGATE_ROUTER_PORT
from cilantro.constants.system_config import *

from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.consensus.sub_block import SubBlockMetaData
from cilantro.messages.consensus.sub_block_contender import SubBlockContender
from cilantro.messages.consensus.merkle_signature import MerkleSignature
from cilantro.messages.block_data.block_data import BlockData
from cilantro.messages.block_data.block_metadata import BlockMetaData, NewBlockNotification
from cilantro.messages.block_data.state_update import StateUpdateReply, StateUpdateRequest
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
        self.curr_block_hash = '0' * 64

        self.run()

    def run(self):
        self.log.info("Block Aggregator starting...")
        self.build_task_list()
        self.loop.run_until_complete(asyncio.gather(*self.tasks))

    def build_task_list(self):
        self.sub = self.manager.create_socket(
            socket_type=zmq.SUB,
            name="BA-Sub-{}".format(self.verifying_key[-8:]),
            secure=True,
            domain="sb-contender"
        )
        self.pub = self.manager.create_socket(
            socket_type=zmq.PUB,
            name="BA-Pub-{}".format(self.verifying_key[-8:]),
            secure=True,
            domain="sb-contender"
        )
        self.router = self.manager.create_socket(
            socket_type=zmq.ROUTER,
            name="BA-Router-{}".format(self.verifying_key[-8:]),
            secure=True,
            domain="sb-contender"
        )
        self.router.setsockopt(zmq.ROUTER_MANDATORY, 1)  # FOR DEBUG ONLY
        self.tasks.append(self.sub.add_handler(self.handle_sub_msg))
        self.tasks.append(self.router.add_handler(self.handle_router_msg))

        self.router.bind(ip=self.ip, port=MASTER_ROUTER_PORT)
        self.pub.bind(ip=self.ip, port=MASTER_PUB_PORT)

        # Listen to delegates for sub block contenders
        self.sub.setsockopt(zmq.SUBSCRIBE, DEFAULT_FILTER.encode())
        for vk in VKBook.get_delegates():
            self.sub.connect(vk=vk, port=DELEGATE_PUB_PORT)
            self.router.connect(vk=vk, port=DELEGATE_ROUTER_PORT)

        for vk in VKBook.get_masternodes():
            if vk != self.verifying_key:
                self.sub.connect(vk=vk, port=MASTER_PUB_PORT)
                self.router.connect(vk=vk, port=MASTER_ROUTER_PORT)

    def handle_sub_msg(self, frames):
        envelope = Envelope.from_bytes(frames[-1])
        msg = envelope.message

        if isinstance(msg, SubBlockContender):
            self.recv_sub_block_contender(msg)
        elif isinstance(msg, NewBlockNotification):
            self.recv_new_block_notif(msg)
        else:
            raise Exception("BlockAggregator got message type {} from SUB socket that it does not know how to handle"
                            .format(type(msg)))

    def handle_router_msg(self, frames):
        envelope = Envelope.from_bytes(frames[-1])
        msg = envelope.message

        if isinstance(msg, StateUpdateRequest):
            self.recv_state_update_request(id_frame=frames[0], req=msg)
        else:
            raise Exception("BlockAggregator got message type {} from ROUTER socket that it does not know how to handle"
                            .format(type(msg)))

    def recv_sub_block_contender(self, sbc: SubBlockContender):
        self.log.info("Received a sbc with result hash {} and input hash {}".format(sbc.result_hash, sbc.input_hash))
        if self.result_hashes.get(sbc.result_hash):
            if self.result_hashes[sbc.result_hash].get('_consensus_reached_') or \
                self.sub_blocks.get(sbc.result_hash):
                self.log.spam('Already validated this SubBlock (result_hash={})'.format(
                    sbc.result_hash))
            elif self.check_alredy_verified(sbc):
                self.log.spam('Already received and verified this SubBlockContender (result_hash={}, input_hash={})'.format(
                    sbc.result_hash, sbc.input_hash))
            else:
                if self.verify_sub_block_contender(sbc):
                    self.log.info('Received SubBlockContender for an existing result hash (result_hash={}, input_hash={})'.format(
                        sbc.result_hash, sbc.input_hash))
                    self.aggregate_sub_block(sbc)
                else:
                    self.log.warning('Not a valid SubBlockContender for existing result hash (result_hash={}, input_hash={})'.format(
                        sbc.result_hash, sbc.input_hash))
        else:
            if self.verify_sub_block_contender(sbc):
                self.log.info('Received SubBlockContender for a new result hash (result_hash={}, input_hash={})'.format(
                    sbc.result_hash, sbc.input_hash))
                self.aggregate_sub_block(sbc)
            else:
                self.log.warning('Not a valid SubBlockContender for new result hash (result_hash={}, input_hash={})'.format(
                    sbc.result_hash, sbc.input_hash))

    def check_alredy_verified(self, sbc: SubBlockContender):
        if sbc.signature.signature in self.result_hashes.get(sbc.result_hash, {}).get('_valid_signatures_'):
            return True
        return False

    def verify_sub_block_contender(self, sbc: SubBlockContender):
        if not sbc.signature.verify(bytes.fromhex(sbc.result_hash)):
            self.log.info('This SubBlockContender does not have a correct signature!')
            return False
        if len(sbc.merkle_leaves) > 0:
            if MerkleTree.verify_tree_from_str(sbc.merkle_leaves, root=sbc.result_hash) \
                and self.validate_transactions(sbc):
                self.log.info('This SubBlockContender is valid!')
                return True
            else:
                self.log.warning('This SubblockContender is INVALID!')
        else:
            self.log.info('This SubBlockContender is empty.')
            return True
        return False

    def validate_transactions(self, sbc):
        for tx in sbc.transactions:
            if not tx.hash in sbc.merkle_leaves:
                self.log.warning('Received malicious transactions that does not match any merkle leaves!')
                return False
        return True

    def aggregate_sub_block(self, sbc):
        if not self.result_hashes.get(sbc.result_hash):
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
        self.result_hashes[sbc.result_hash]['_valid_signatures_'][sbc.signature.signature] = sbc.signature
        for tx in sbc.transactions:
            self.result_hashes[sbc.result_hash]['_transactions_'][tx.hash] = tx
        if len(self.result_hashes[sbc.result_hash]['_valid_signatures_']) >= DELEGATE_MAJORITY \
            and len(self.result_hashes[sbc.result_hash]['_transactions_']) == \
                len(self.result_hashes[sbc.result_hash]['_merkle_leaves_']):
            self.log.info('SubBlock is validated and consensus reached (result_hash={})'.format(sbc.result_hash))
            self.result_hashes[sbc.result_hash]['_consensus_reached_'] = True
            self.store_sub_block(sbc, self.result_hashes[sbc.result_hash]['_valid_signatures_'].values())
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
        self.result_hashes = {
             result_hash: self.result_hashes[result_hash] \
                for result_hash in self.result_hashes \
                if self.result_hashes[result_hash]['_lastest_valid_'] <= SUB_BLOCK_VALID_PERIOD + time.time() and \
                    not self.result_hashes[result_hash].get('_committed_')
        }

    def store_sub_block(self, sbc: SubBlockContender, signatures: List[MerkleSignature]):
        StorageDriver.store_sub_block(sbc, list(signatures))

    def store_full_block(self):
        sub_blocks = {
            result_hash: self.result_hashes[result_hash] for result_hash in self.result_hashes \
                if self.result_hashes[result_hash].get('_consensus_reached_')
        }
        if len(sub_blocks) < NUM_SB_PER_BLOCK:
            self.log.info('Received {}/{} required sub-blocks so far.'.format(
                len(sub_blocks), NUM_SB_PER_BLOCK))
        else:

            unordered_merkle_roots = [result_hash for result_hash in sub_blocks][:NUM_SB_PER_BLOCK]
            merkle_roots = sorted(unordered_merkle_roots, key=lambda result_hash: self.result_hashes[result_hash]['_sb_index_'])
            input_hashes = [self.result_hashes[result_hash]['_input_hash_'] for result_hash in merkle_roots]
            transactions = list(itertools.chain.from_iterable([sub_blocks[mr]['_transactions_'].values() for mr in merkle_roots]))
            prev_block_hash = StorageDriver.get_latest_block_hash()
            block_hash = BlockData.compute_block_hash(sbc_roots=merkle_roots, prev_block_hash=prev_block_hash)
            sig = MerkleSignature.create(sig_hex=wallet.sign(self.signing_key, block_hash.encode()),
                                         sender=self.verifying_key, timestamp=str(time.time()))
            block_data = BlockData.create(block_hash=block_hash, prev_block_hash=prev_block_hash,
                                          transactions=transactions, masternode_signature=sig,
                                          merkle_roots=merkle_roots, input_hashes=input_hashes)

            self.log.info("Attempting to store block with hash {} and prev_block_hash {}".format(block_hash, prev_block_hash))
            # DEBUG Development sanity checks
            assert prev_block_hash == self.curr_block_hash, "Current block hash {} does not match StorageDriver previous " \
                                                            "block hash {}".format(self.curr_block_hash, prev_block_hash)
            assert len(merkle_roots) == NUM_SB_PER_BLOCK, "Aggregator has {} merkle roots but there are {} SBs/per/block" \
                                                          .format(len(merkle_roots), NUM_SB_PER_BLOCK)
            # TODO wrap storage in try/catch. Add logic for storage failure
            StorageDriver.store_block(block_data)
            self.curr_block_hash = block_hash
            self.log.success("STORED BLOCK WITH HASH {}".format(block_hash))
            self.send_new_block_notification(block_data)
            for result_hash in merkle_roots:
                self.sub_blocks[result_hash] = True
                self.result_hashes[result_hash]['_committed_'] = True

    def send_new_block_notification(self, block_data):
        new_block_notif = NewBlockNotification.create_from_block_data(block_data)
        block_hash = block_data.block_hash
        if self.full_blocks.get(block_hash):
            self.log.info('Already received block hash "{}", adding to consensus count.'.format(block_hash))
        else:
            self.log.info('Created resultant block-hash "{}"'.format(block_hash))
            self.full_blocks[block_hash] = {
                '_block_metadata_': new_block_notif,
                '_consensus_reached_': False,
                '_master_signatures_': {block_data.masternode_signature.signature: block_data.masternode_signature}
            }

        self.pub.send_msg(msg=new_block_notif, header=DEFAULT_FILTER.encode())

        return new_block_notif

    def recv_new_block_notif(self, nbc: NewBlockNotification):
        block_hash = nbc.block_hash
        signature = nbc.masternode_signature
        if not self.full_blocks.get(block_hash):
            self.log.info('Received NEW block hash "{}", did not yet receive valid sub blocks from delegates.'.format(block_hash))
            self.full_blocks[block_hash] = {
                '_block_metadata_': nbc,
                '_consensus_reached_': False,
                '_master_signatures_': {signature.signature: signature}
            }
        elif signature.signature in self.full_blocks[block_hash]['_master_signatures_']:
            self.log.warning('Already received the NewBlockNotification with block_hash "{}"'.format(block_hash))
        elif self.full_blocks[block_hash].get('consensus_reached') != True:
            self.log.info('Received KNOWN block hash "{}", adding to consensus count.'.format(block_hash))
            self.full_blocks[block_hash]['_master_signatures_'][signature.signature] = signature
            if len(self.full_blocks[block_hash]['_master_signatures_']) >= MASTERNODE_MAJORITY:
                self.full_blocks[block_hash]['_consensus_reached_'] = True
                bmd = self.full_blocks[block_hash].get('_block_metadata_')
                if not len(bmd.merkle_roots) == NUM_SB_PER_BLOCK:
                    # TODO Request blocks from other masternodes
                    pass
        else:
            self.log.info('Received KNOWN block hash "{}" but consensus already reached.'.format(block_hash))

    def recv_state_update_request(self, id_frame: bytes, req: StateUpdateRequest):
        blocks = StorageDriver.get_latest_blocks(req.block_hash)
        reply = StateUpdateReply.create(blocks)
        self.router.send_multipart([])
