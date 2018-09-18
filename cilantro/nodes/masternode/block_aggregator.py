from cilantro.nodes.delegate.sub_block_builder import SubBlockBuilder
from cilantro.storage.blocks import BlockStorageDriver
from cilantro.logger.base import get_logger
from cilantro.storage.db import VKBook
from cilantro.protocol.multiprocessing.worker import Worker
from cilantro.utils.lprocess import LProcess

from cilantro.constants.nodes import *
from cilantro.constants.zmq_filters import MASTERNODE_DELEGATE_FILTER, MASTER_MASTER_FILTER
from cilantro.constants.ports import MN_SUB_BLOCK_PORT, INTER_MASTER_PORT
from cilantro.constants.delegate import NODES_REQUIRED_CONSENSUS, TOP_DELEGATES

from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.consensus.block_contender import BlockContender
from cilantro.messages.block_data.block_metadata import NewBlockNotification
from cilantro.messages.block_data.main_block import MainBlock
from cilantro.utils.hasher import Hasher

import asyncio, zmq, os, heapq
from collections import defaultdict

class ResultHash(bytes):
    pass

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
        self.merkle_hashes_required = 0
        self.signatures_received = set()
        self.merkle_hashes_received = set()

    def handle_sub_msg(self, frames):
        envelope = Envelope.from_bytes(frames[-1])
        msg = envelope.message

        if isinstance(msg, SubBlockContender):
            self.recv_sub_block_contender(msg)
        elif isinstance(msg, ResultHash):
            self.recv_result_hash(msg)
        else:
            raise Exception("BlockManager got message type {} from SUB socket that it does not know how to handle"
                            .format(type(msg)))
        # Last frame, frames[-1] will be the envelope binary

    def recv_sub_block_contender(self, sbc: SubBlockContender):
        cached_sbc = self.contenders.get(sbc._data.resultHash)
        if not cached_sbc:
            self.contenders[sbc._data.resultHash] = {
                'result_hash': sbc._data.resultHash,
                'input_hash': sbc._data.inputHash,
                'merkle_leaves': sbc._data.merkleLeaves,
                'signatures': [sbc._data.signature],
                'transactions': sbc._data.transactions
            }
            self.merkle_hashes_required = len(sbc._data.merkleLeaves)
            self.log.important('Validated and stored SubBlockContender {}'.format(sbc))
        elif sbc == cached_sbc:
            self.contenders[sbc._data.resultHash]['signatures'].append(sbc._data.signature)
            self.log.important('Received from another delegate for SubBlockContender {}'.format(sbc))
        else:
            return
        for tx in sbc._data.transactions:
            self.merkle_hashes_received.add(Hasher.hash(tx))
            self.signatures_received.add(sbc._data.signature)
        self.prepare_main_block()

    def prepare_main_block(self):
        self.log.info('Received {}/{} ({} required) signatures and {}/{} total transactions'.format(
            self.total_signatures, TOP_DELEGATES, NODES_REQUIRED_CONSENSUS,
            len(self.merkle_hashes_received), self.merkle_hashes_required
        ))
        if self.total_signatures >= NODES_REQUIRED_CONSENSUS and \
            self.merkle_hashes_received == self.merkle_hashes_required:
            contender_hashes = ''.join(self.contenders.keys().sort()).encode()
            self.log.critical('##TODO## PREPARING RESULT HASH: {}'.format(self.contenders))
            # send result_hash

    def recv_result_hash(self, result_hash: ResultHash):
        # TODO Check result_hash
        pass
