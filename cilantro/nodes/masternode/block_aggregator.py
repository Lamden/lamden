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

import asyncio, zmq, os, time
from collections import defaultdict

class BlockAggregator(Worker):

    def __init__(self, ip, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = get_logger("BlockAggregator[{}]".format(self.verifying_key[:8]))
        self.ip = ip
        self.tasks = []
        self.contenders = {}
        self.result_hashes = {}
        self.full_block_hashes = {}
        self.total_valid_sub_blocks = 0
        self.curr_block_hash = '0' * 64 # TODO: Change this to the genesis block hash
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
        # Last frame, frames[-1] will be the envelope binary

    def handle_router_msg(self, frames):
        envelope = Envelope.from_bytes(frames[-1])
        msg = envelope.message

        if isinstance(msg, StateUpdateRequest):
            self.recv_state_update_request(id_frame=frames[0], req=msg)
        else:
            raise Exception("BlockAggregator got message type {} from ROUTER socket that it does not know how to handle"
                            .format(type(msg)))

    def recv_sub_block_contender(self, sbc: SubBlockContender):
        result_hash = sbc.result_hash
        input_hash = sbc.input_hash
        self.log.info("Received a sbc with result hash {} and input hash {}".format(result_hash, input_hash))
        cached = self.contenders.get(input_hash)
        if not cached:
            if MerkleTree.verify_tree_from_str(sbc.merkle_leaves, root=sbc.result_hash):
                self.contenders[input_hash] = {
                    'merkle_leaves': sbc.merkle_leaves,
                    'transactions': set(),
                    'received_count': 0
                }
            else:
                self.log.fatal('Received a SubBlockContender with invalid merkle tree!')
                return
        if self.result_hashes.get(result_hash) and self.result_hashes[result_hash]['consensus_reached'] == True:
            self.log.info('Received from a delegate for SubBlockContender that has already reached consensus on sub block level')
            return
        else:
            self.log.spam('Received from another delegate for SubBlockContender {}'.format(sbc))

        self.contenders[input_hash]['received_count'] += 1
        if not self.result_hashes.get(result_hash):
            self.result_hashes[result_hash] = {'signatures': {}, 'input_hashes': set(), 'consensus_reached': False, 'sb_index': sbc.sb_index}
        self.result_hashes[result_hash]['signatures'][sbc._data.signature] = sbc.signature
        self.result_hashes[result_hash]['input_hashes'].add(input_hash)

        for tx in sbc.transactions:
            merkle_leaf = tx.hash
            if not merkle_leaf in self.contenders[input_hash]['merkle_leaves']:
                self.log.warning('Received malicious transactions that does not match any merkle leaves!')
                if len(self.result_hashes[result_hash]['signatures']) == 1:
                    del self.result_hashes[result_hash] # Remove bad actor to save space
                    # TODO: Log bad actor info
                return
            else:
                self.contenders[input_hash]['transactions'].add(tx)
                self.log.spam('Received {}/{} transactions!'.format(
                    len(self.contenders[input_hash]['transactions']), len(self.contenders[input_hash]['merkle_leaves'])
                ))

        self.combine_result_hash(input_hash)

    def combine_result_hash(self, input_hash):
        if self.contenders.get(input_hash):
            result_hashes = []
            for result_hash in self.result_hashes:
                if input_hash in self.result_hashes[result_hash]['input_hashes']:
                    signatures = self.result_hashes[result_hash]['signatures']
                    self.log.info('Received {}/{} ({} required) signatures'.format(
                        len(signatures), NUM_DELEGATES, DELEGATE_MAJORITY
                    ))
                    if len(signatures) >= DELEGATE_MAJORITY:
                        if len(self.contenders[input_hash]['transactions']) == len(self.contenders[input_hash]['merkle_leaves']):
                            self.log.info('Sub block consensus reached, all transactions present.')
                            self.total_valid_sub_blocks += 1
                            self.result_hashes[result_hash]['consensus_reached'] = True
                            if self.total_valid_sub_blocks >= NUM_SB_PER_BLOCK:
                                result_hashes = [h for h in self.result_hashes if self.result_hashes[h]['consensus_reached']]
                                new_block_notif = self.store_full_block(result_hashes)
                                self.log.notice("Sending new block notification!")
                                self.pub.send_msg(msg=new_block_notif, header=DEFAULT_FILTER.encode())
                                break
                        elif self.contenders[input_hash]['received_count'] == NUM_DELEGATES:
                            self.log.error('Received sub blocks from all delegates and still have missing transactions!')
                            raise Exception('Received sub blocks from all delegates and still have missing transactions!') # DEBUG
            for rh in result_hashes:
                del self.result_hashes[rh]

    def recv_new_block_notif(self, nbc: NewBlockNotification):
        block_hash = nbc.block_hash

        if not self.full_block_hashes.get(block_hash):
            self.log.info('Received NEW block hash "{}", did not yet receive valid sub blocks from delegates.'.format(block_hash))
            self.full_block_hashes[block_hash] = {
                'consensus_count': 1,
                'full_block_metadata': nbc
            }
        elif self.full_block_hashes[block_hash].get('consensus_reached') != True:
            self.total_valid_sub_blocks = 0
            self.log.info('Received KNOWN block hash "{}", adding to consensus count.'.format(block_hash))
            self.full_block_hashes[block_hash]['consensus_count'] += 1
            if self.full_block_hashes[block_hash]['consensus_count'] >= MASTERNODE_MAJORITY:
                self.full_block_hashes[block_hash]['consensus_reached'] = True
                bmd = self.full_block_hashes[block_hash].get('full_block_metadata')
                if not len(bmd.merkle_roots) == NUM_SB_PER_BLOCK:
                    # TODO Request blocks from other masternodes
                    pass
        else:
            self.log.info('Received KNOWN block hash "{}" but consensus already reached.'.format(block_hash))

    def store_full_block(self, hash_list: List[str]) -> NewBlockNotification:
        merkle_roots = sorted(hash_list, key=lambda result_hash: self.result_hashes[result_hash]['sb_index'])
        input_hashes = [self.result_hashes[root]['input_hashes'][0] for root in merkle_roots]
        sub_block_metadatas, all_signatures, all_merkle_leaves, all_transactions = self.combine_sub_blocks(merkle_roots)
        prev_block_hash = StorageDriver.get_latest_block_hash()
        block_hash = BlockData.compute_block_hash(sbc_roots=merkle_roots, prev_block_hash=prev_block_hash)
        sig = MerkleSignature.create(sig_hex=wallet.sign(self.signing_key, block_hash.encode()),
                                     sender=self.verifying_key, timestamp=str(time.time()))

        # Development sanity checks
        assert prev_block_hash == self.curr_block_hash, "Current block hash {} does not match StorageDriver previous " \
                                                        "block hash {}".format(self.curr_block_hash, prev_block_hash)
        assert len(merkle_roots) == NUM_SB_PER_BLOCK, "Aggregator has {} merkle roots but there are {} SBs/per/block" \
                                                      .format(len(merkle_roots), NUM_SB_PER_BLOCK)

        self.log.info("Attempting to store block with hash {} and prev_block_hash {}".format(block_hash, prev_block_hash))
        block_data = BlockData.create(block_hash=block_hash, prev_block_hash=prev_block_hash,
                                      transactions=all_transactions, masternode_signature=sig,
                                      merkle_roots=merkle_roots)

        # TODO wrap storage in try/catch. Add logic for storage failure
        StorageDriver.store_block(block_data)
        self.log.success("STORED BLOCK WITH HASH {}".format(block_hash))

        self.curr_block_hash = block_hash

        new_block_notif = NewBlockNotification.create(block_hash=block_data.block_hash, merkle_roots=block_data.merkle_roots,
                                                      prev_block_hash=block_data.prev_block_hash,
                                                      masternode_signature=block_data.masternode_signature,
                                                      input_hashes=input_hashes)

        if self.full_block_hashes.get(block_hash):
            self.log.info('Already received block hash "{}", adding to consensus count.'.format(block_hash))
            self.full_block_hashes[block_hash]['consensus_count'] += 1
        else:
            self.log.info('Created resultant block-hash "{}"'.format(block_hash))
            self.full_block_hashes[block_hash] = {
                'consensus_count': 1,
                'full_block_metadata': new_block_notif
            }

        return new_block_notif

    def combine_sub_blocks(self, merkle_roots):
        sub_block_metadatas = []
        all_merkle_leaves = []
        all_signatures = []
        all_transactions = []

        for idx, result_hash in enumerate(merkle_roots):
            for input_hash in self.result_hashes[result_hash]['input_hashes']:
                merkle_leaves = self.contenders[input_hash]['merkle_leaves']
                all_transactions += self.contenders[input_hash]['transactions']
                all_merkle_leaves += merkle_leaves
                all_signatures += list(self.result_hashes[result_hash]['signatures'].values())
                sub_block_metadatas.append(SubBlockMetaData.create(
                    merkle_root=result_hash,
                    signatures=list(self.result_hashes[result_hash]['signatures'].keys()),
                    merkle_leaves=merkle_leaves,
                    sub_block_idx=idx))
        return sub_block_metadatas, all_signatures, all_merkle_leaves, all_transactions

    def recv_state_update_request(self, id_frame: bytes, req: StateUpdateRequest):
        blocks = StorageDriver.get_latest_blocks(req.block_hash)
        reply = StateUpdateReply.create(blocks)
        self.router.send_multipart([])
