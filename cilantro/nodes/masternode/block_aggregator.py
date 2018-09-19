from cilantro.logger.base import get_logger
from cilantro.storage.db import VKBook
from cilantro.protocol.multiprocessing.worker import Worker

from cilantro.constants.zmq_filters import MASTERNODE_DELEGATE_FILTER, MASTER_MASTER_FILTER
from cilantro.constants.ports import MN_SUB_BLOCK_PORT, INTER_MASTER_PORT
from cilantro.constants.delegate import NODES_REQUIRED_CONSENSUS, TOP_DELEGATES
from cilantro.constants.masternode import NODES_REQUIRED_CONSENSUS as MASTERNODE_REQUIRED_CONSENSUS, SUBBLOCKS_REQUIRED

from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.consensus.full_block_hash import FullBlockHash
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
        elif isinstance(msg, FullBlockHash):
            self.recv_result_hash(msg)
        else:
            raise Exception("BlockManager got message type {} from SUB socket that it does not know how to handle"
                            .format(type(msg)))
        # Last frame, frames[-1] will be the envelope binary

    def recv_sub_block_contender(self, sbc: SubBlockContender):
        sbc.validate()
        result_hash = sbc._data.resultHash
        cached = self.contenders.get(result_hash)
        if not cached:
            self.contenders[result_hash] = {
                'signatures_received': set(),
                'merkle_hashes_received': set(),
                'sbc': sbc,
                'merkle_hashes_required': len(sbc._data.merkleLeaves)
            }
            self.log.spam('Validated and stored SubBlockContender {}'.format(sbc))
        elif sbc == cached['sbc']:
            self.contenders[result_hash]['signatures_received'].add(sbc._data.signature)
            self.log.spam('Received from another delegate for SubBlockContender {}'.format(sbc))
        else:
            return
        for tx in sbc._data.transactions:
            self.contenders[result_hash]['merkle_hashes_received'].add(Hasher.hash(tx))
            self.contenders[result_hash]['signatures_received'].add(sbc._data.signature)
        self.combine_result_hash(result_hash)

    def combine_result_hash(self, result_hash):
        self.log.info('Received {}/{} ({} required) signatures and {}/{} total transactions'.format(
            len(self.contenders[result_hash]['signatures_received']), TOP_DELEGATES, NODES_REQUIRED_CONSENSUS,
            len(self.contenders[result_hash]['merkle_hashes_received']), self.contenders[result_hash]['merkle_hashes_required']
        ))
        if len(self.contenders[result_hash]['signatures_received']) >= NODES_REQUIRED_CONSENSUS and \
            len(self.contenders[result_hash]['merkle_hashes_received']) == self.contenders[result_hash]['merkle_hashes_required']:
            self.total_valid_sub_blocks += 1
            if self.total_valid_sub_blocks >= SUBBLOCKS_REQUIRED:
                fbh = FullBlockHash.create(b''.join(sorted(self.contenders.keys())))
                full_block_hash = fbh._data.fullBlockHash
                self.log.important('Created resultant block-hash: {}'.format(full_block_hash))
                self.full_block_hashes[full_block_hash] = 1
                self.pub.send_msg(msg=full_block_hash, header=MASTER_MASTER_FILTER.encode())

    def recv_result_hash(self, full_block_hash: FullBlockHash):
        full_block_hash.validate()
        if not self.full_block_hashes.get(full_block_hash):
            self.full_block_hashes[full_block_hash] = 1
        else:
            self.full_block_hashes[full_block_hash] += 1
            if self.full_block_hashes[full_block_hash] >= MASTERNODE_REQUIRED_CONSENSUS:
                # TODO
                # 1. build merkle tree
                # 2. commit the block to db
                # 3. Delete it from self.contenders
                # 4. Delete it from self.full_block_hashes
                self.total_valid_sub_blocks = 0
