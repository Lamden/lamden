from cilantro.logger.base import get_logger
from cilantro.storage.db import VKBook
from cilantro.protocol.multiprocessing.worker import Worker
from cilantro.protocol.structures.merkle_tree import MerkleTree

from cilantro.constants.zmq_filters import MASTERNODE_DELEGATE_FILTER, MASTER_MASTER_FILTER, DEFAULT_FILTER
from cilantro.constants.ports import MASTER_ROUTER_PORT, MASTER_PUB_PORT, DELEGATE_PUB_PORT, DELEGATE_ROUTER_PORT
from cilantro.constants.delegate import NODES_REQUIRED_CONSENSUS, TOP_DELEGATES
from cilantro.constants.masternode import NODES_REQUIRED_CONSENSUS as MASTERNODE_REQUIRED_CONSENSUS, SUBBLOCKS_REQUIRED

from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.consensus.sub_block import SubBlockMetaData
from cilantro.messages.consensus.sub_block_contender import SubBlockContender
from cilantro.messages.consensus.block_contender import BlockContender
from cilantro.storage.blocks import BlockStorageDriver
from cilantro.messages.block_data.block_data import BlockData
from cilantro.messages.block_data.block_metadata import BlockMetaData
from cilantro.messages.block_data.state_update import StateUpdateReply, StateUpdateRequest
from cilantro.utils.hasher import Hasher
from cilantro.protocol import wallet

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
        elif isinstance(msg, BlockMetaData):
            self.recv_full_block_hash_metadata(msg)
        else:
            raise Exception("BlockAggregator got message type {} from SUB socket that it does not know how to handle"
                            .format(type(msg)))
        # Last frame, frames[-1] will be the envelope binary

    def handle_router_msg(self):
        envelope = Envelope.from_bytes(frames[-1])
        msg = envelope.message

        if isinstance(msg, StateUpdateRequest):
            raise Exception('Received StateUpdateRequest but NOT IMPLEMENTED')
        else:
            raise Exception("BlockAggregator got message type {} from ROUTER socket that it does not know how to handle"
                            .format(type(msg)))

    def recv_sub_block_contender(self, sbc: SubBlockContender):
        sbc.validate()
        result_hash = sbc.result_hash
        input_hash = sbc.input_hash
        cached = self.contenders.get(input_hash)
        if not cached:
            # if MerkleTree.verify_tree(leaves=sbc.merkle_leaves, root=sbc.result_hash, hash_leaves=False):
            if MerkleTree.verify_tree_from_hex_str(''.join(sbc.merkle_leaves), root=sbc.result_hash):
                self.contenders[input_hash] = {
                    'merkle_leaves': sbc.merkle_leaves,
                    'transactions': set(),
                    'sb_index': sbc.sb_index,
                    'received_count': 0
                }
                self.log.spam('Received and validated SubBlockContender {}'.format(sbc))
            else:
                self.log.warning('SubBlockContender yields invalid tree!')
                return
        elif cached.get('consensus_reached'):
            self.log.info('Received from a delegate for SubBlockContender that has already reached consensus on sub block level')
            return
        else:
            self.log.spam('Received from another delegate for SubBlockContender {}'.format(sbc))

        self.contenders[input_hash]['received_count'] += 1
        if not self.result_hashes.get(result_hash):
            self.result_hashes[result_hash] = {'signatures': {}, 'input_hash': input_hash}
        self.result_hashes[result_hash]['signatures'][sbc._data.signature] = sbc.signature

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
                self.log.warning('Received {}/{} transactions!'.format(
                    len(self.contenders[input_hash]['transactions']), len(self.contenders[input_hash]['merkle_leaves'])
                ))
        self.combine_result_hash(input_hash)

    def combine_result_hash(self, input_hash):
        if self.contenders.get(input_hash):
            for result_hash in self.result_hashes:
                if self.result_hashes[result_hash]['input_hash'] == input_hash:
                    signatures = self.result_hashes[result_hash]['signatures']
                    self.log.info('Received {}/{} ({} required) signatures'.format(
                        len(signatures), TOP_DELEGATES, NODES_REQUIRED_CONSENSUS
                    ))
                    if len(signatures) >= NODES_REQUIRED_CONSENSUS:
                        if len(self.contenders[input_hash]['transactions']) == len(self.contenders[input_hash]['merkle_leaves']):
                            self.log.info('Sub block consensus reached, all transactions present.')
                            self.total_valid_sub_blocks += 1
                            if self.total_valid_sub_blocks >= SUBBLOCKS_REQUIRED:
                                self.contenders[input_hash]['consensus_reached'] = True
                                block, bmd, sbmd = self.store_full_block(self.contenders.keys())
                                self.pub.send_msg(msg=bmd, header=DEFAULT_FILTER.encode())
                        elif self.contenders[input_hash]['received_count'] == TOP_DELEGATES:
                            self.log.error('Received sub blocks from all delegates and still have missing transactions!')
                            raise Exception('Received sub blocks from all delegates and still have missing transactions!') # DEBUG

    def recv_full_block_hash_metadata(self, bmd: BlockMetaData):
        bmd.validate()
        block_hash = bmd.block_hash
        if not self.full_block_hashes.get(block_hash):
            self.log.info('Received NEW block hash "{}", did not yet receive valid sub blocks from delegates.'.format(block_hash))
            self.full_block_hashes[block_hash] = {
                'consensus_count': 1,
                'full_block_metadata': bmd
            }
        elif self.full_block_hashes[block_hash].get('consensus_reached') != True:
            self.total_valid_sub_blocks = 0
            self.log.info('Received KNOWN block hash "{}", adding to consensus count.'.format(block_hash))
            self.full_block_hashes[block_hash]['consensus_count'] += 1
            if self.full_block_hashes[block_hash]['consensus_count'] >= MASTERNODE_REQUIRED_CONSENSUS:
                self.full_block_hashes[block_hash]['consensus_reached'] = True
                bmd = self.full_block_hashes[block_hash].get('full_block_metadata')
                if not len(bmd.merkle_roots) == SUBBLOCKS_REQUIRED:
                    # TODO Request blocks from other masternodes
                    pass
        else:
            self.log.info('Received KNOWN block hash "{}" but consensus already reached.'.format(block_hash))

    def store_full_block(self, hash_list):
        merkle_roots = sorted(hash_list, key=lambda input_hash: self.contenders[input_hash]['sb_index'])
        sub_block_metadatas, all_signatures, all_merkle_leaves, all_transactions = self.combine_sub_blocks(merkle_roots)

        prev_block_hash = self.curr_block_hash
        block = BlockContender.create(
            signatures=all_signatures,
            merkle_leaves=all_merkle_leaves,
            prev_block_hash=prev_block_hash
        )
        block_hash, signature = BlockStorageDriver.store_block(
            block_contender=block,
            raw_transactions=all_transactions,
            publisher_sk=self.signing_key,
            no_validate=True
        )
        block_metadata = BlockMetaData.create(
            block_hash=block_hash,
            merkle_roots=merkle_roots,
            prev_block_hash=self.curr_block_hash,
            masternode_signature=signature
        )
        self.curr_block_hash = block_hash

        if self.full_block_hashes.get(block_hash):
            self.log.info('Already received block hash "{}", adding to consensus count.'.format(block_hash))
            self.full_block_hashes[block_hash]['consensus_count'] += 1
        else:
            self.log.important('Created resultant block-hash "{}"'.format(block_hash))
            self.full_block_hashes[block_hash] = {
                'consensus_count': 1,
                'full_block_metadata': block_metadata
            }

        return block, block_metadata, sub_block_metadatas

    def combine_sub_blocks(self, merkle_roots):
        sub_block_metadatas = []
        all_merkle_leaves = []
        all_signatures = []
        all_transactions = []
        for idx, input_hash in enumerate(merkle_roots):
            for result_hash in self.result_hashes:
                if not input_hash == self.result_hashes[result_hash]['input_hash']: continue
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

    def recv_state_update_request(self):
        pass
