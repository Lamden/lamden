from cilantro.logger.base import get_logger
from cilantro.storage.db import VKBook
from cilantro.protocol.multiprocessing.worker import Worker
from cilantro.protocol.structures.merkle_tree import MerkleTree

from cilantro.constants.zmq_filters import MASTERNODE_DELEGATE_FILTER, MASTER_MASTER_FILTER
from cilantro.constants.ports import MN_SUB_BLOCK_PORT, INTER_MASTER_PORT
from cilantro.constants.delegate import NODES_REQUIRED_CONSENSUS, TOP_DELEGATES
from cilantro.constants.masternode import NODES_REQUIRED_CONSENSUS as MASTERNODE_REQUIRED_CONSENSUS, SUBBLOCKS_REQUIRED

from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.consensus.sub_block import SubBlockHashes
from cilantro.messages.consensus.sub_block_contender import SubBlockContender
from cilantro.utils.hasher import Hasher

import asyncio, zmq, os, heapq
from collections import defaultdict

class BlockAggregator(Worker):

    def __init__(self, ip, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = get_logger("BlockAggregator[{}]".format(self.verifying_key[:8]))
        self.ip = ip
        self.tasks = []
        self.reset()
        self.run()

    def run(self):
        self.log.info("Block Aggregator starting...")
        self.build_task_list()
        self.loop.run_until_complete(asyncio.gather(*self.tasks))

    def build_task_list(self):
        self.sub = self.manager.create_socket(
            socket_type=zmq.SUB,
            name="BA-Sub-{}".format(self.verifying_key),
            secure=True,
            domain="sb-contender"
        )
        self.pub = self.manager.create_socket(
            socket_type=zmq.PUB,
            name="BA-Pub-{}".format(self.verifying_key),
            secure=True,
            domain="sb-contender"
        )
        self.tasks.append(self.sub.add_handler(self.handle_sub_msg))

        # Listen to delegates for sub block contenders
        self.sub.setsockopt(zmq.SUBSCRIBE, MASTERNODE_DELEGATE_FILTER.encode())
        for vk in VKBook.get_delegates():
            self.sub.connect(vk=vk, port=MN_SUB_BLOCK_PORT)

        self.sub.setsockopt(zmq.SUBSCRIBE, MASTER_MASTER_FILTER.encode())
        for vk in VKBook.get_masternodes():
            if vk != self.verifying_key:  # Do not SUB to itself
                self.sub.connect(vk=vk, port=INTER_MASTER_PORT)

        self.pub.bind(ip=self.ip, port=INTER_MASTER_PORT)

    def reset(self):
        self.contenders = {}
        self.full_block_hashes = {}
        self.total_valid_sub_blocks = 0

    def handle_sub_msg(self, frames):
        envelope = Envelope.from_bytes(frames[-1])
        msg = envelope.message

        if isinstance(msg, SubBlockContender):
            self.recv_sub_block_contender(msg)
        elif isinstance(msg, SubBlockHashes):
            self.recv_result_hash(msg)
        else:
            raise Exception("BlockManager got message type {} from SUB socket that it does not know how to handle"
                            .format(type(msg)))
        # Last frame, frames[-1] will be the envelope binary

    def recv_sub_block_contender(self, sbc: SubBlockContender):
        sbc.validate()
        result_hash = sbc._data.resultHash
        input_hash = sbc._data.inputHash
        cached = self.contenders.get(input_hash)
        if not cached:
            if MerkleTree.verify_tree(leaves=sbc._data.merkleLeaves, root=result_hash):
                self.contenders[input_hash] = {
                    'result_hashes': {},
                    'merkle_leaves': sbc._data.merkleLeaves
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

        if not self.contenders[input_hash]['result_hashes'].get(result_hash):
            self.contenders[input_hash]['result_hashes'][result_hash] = {'signatures_received': set()}
        self.contenders[input_hash]['result_hashes'][result_hash]['signatures_received'].add(sbc._data.signature)

        for tx in sbc._data.transactions:
            merkle_hash = MerkleTree.hash(tx)
            if not merkle_hash in self.contenders[input_hash]['merkle_leaves']:
                self.log.warning('Received malicious transactions that does not match any merkle leaves!')
                return
        self.combine_result_hash(input_hash)

    def combine_result_hash(self, input_hash):
        if self.contenders.get(input_hash):
            result_hashes = self.contenders[input_hash]['result_hashes']
            for result_hash in result_hashes:
                signatures = self.contenders[input_hash]['result_hashes'][result_hash]['signatures_received']
                self.log.info('Received {}/{} ({} required) signatures'.format(
                    len(signatures), TOP_DELEGATES, NODES_REQUIRED_CONSENSUS
                ))
                if len(signatures) >= NODES_REQUIRED_CONSENSUS:
                    self.total_valid_sub_blocks += 1
                    if self.total_valid_sub_blocks >= SUBBLOCKS_REQUIRED:
                        sbh = SubBlockHashes.create(self.contenders.keys())
                        sub_block_hashes = sbh.sub_block_hashes
                        full_block_hash = sbh.full_block_hash
                        if self.full_block_hashes.get(full_block_hash):
                            self.log.info('Already received block hash "{}", adding to consensus count.'.format(full_block_hash))
                            self.full_block_hashes[full_block_hash]['consensus_count'] += 1
                        else:
                            self.log.important('Created resultant block-hash "{}"'.format(full_block_hash))
                            self.full_block_hashes[full_block_hash] = {
                                'valid_sub_blocks': self.contenders[input_hash],
                                'consensus_count': 1,
                                'sub_block_hashes': sub_block_hashes
                            }
                        self.contenders[input_hash]['consensus_reached'] = True
                        self.pub.send_msg(msg=sbh, header=MASTER_MASTER_FILTER.encode())

    def recv_result_hash(self, sbh: SubBlockHashes):
        sbh.validate()
        full_block_hash = sbh.full_block_hash
        if not self.full_block_hashes.get(full_block_hash):
            self.log.info('Received NEW block hash "{}", did not yet receive valid sub blocks from delegates.'.format(full_block_hash))
            self.full_block_hashes[full_block_hash] = {
                'consensus_count': 1,
                'sub_block_hashes': sbh.sub_block_hashes
            }
        elif self.full_block_hashes[full_block_hash].get('consensus_reached') != True:
            self.total_valid_sub_blocks = 0
            self.log.info('Received KNOWN block hash "{}", adding to consensus count.'.format(full_block_hash))
            self.full_block_hashes[full_block_hash]['consensus_count'] += 1
            if self.full_block_hashes[full_block_hash]['consensus_count'] >= MASTERNODE_REQUIRED_CONSENSUS:
                self.full_block_hashes[full_block_hash]['consensus_reached'] = True
                if not len(self.full_block_hashes[full_block_hash].get('valid_sub_blocks')) == SUBBLOCKS_REQUIRED:
                    # TODO Request sub-blocks from other masternodes
                    pass
                else:
                    # TODO Store sub-blocks, block and transactions in DB
                    # SubBlocks: (merkle_root, signatures, merkle_leaves, index)
                    # Block: (block_hash, merkle_roots, prev_block_hash, timestamp, signature)
                    # Transactions: (tx_hash, blob, status, state)
                    pass
        else:
            self.log.info('Received KNOWN block hash "{}" but consensus already reached.'.format(full_block_hash))
