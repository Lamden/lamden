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

class BlockAggregator(Worker):

    def __init__(self, delegate_vks=[], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = get_logger("BlockAggregator[{}]".format(self.verifying_key[:8]))
        self.tasks = []
        self.contenders = {}
        self.run()

    def run(self):
        self.log.info("Block Aggregator starting...")
        self.build_task_list()
        self.loop.run_until_complete(asyncio.gather(*self.tasks))

    def build_task_list(self):
        self.sub = self.manager.create_socket(
            socket_type=zmq.SUB,
            name="BA-Sub-{}".foramt(vk),
            secure=True,
            domain="sb-contender"
        )
        self.pub = self.manager.create_socket(
            socket_type=zmq.PUB,
            name="BA-Pub-{}".format(vk),
            secure=True,
            domain="sb-contender"
        )
        self.tasks.append(self.sub.add_handler(self.handle_sub_msg))

        # Listen to delegates for sub block contenders
        self.sub.setsockopt(zmq.SUBSCRIBE, MASTERNODE_DELEGATE_FILTER.encode())
        for vk in VKBook.get_delegates():
            if vk != self.verifying_key:  # Do not SUB to itself
                self.sub.connect(vk=vk, port=MN_SUB_BLOCK_PORT)

        self.sub.setsockopt(zmq.SUBSCRIBE, MASTER_MASTER_FILTER.encode())
        for vk in VKBook.get_masternodes():
            if vk != self.verifying_key:  # Do not SUB to itself
                self.sub.connect(vk=vk, port=INTER_MASTER_PORT)

        self.pub.bind(vk=vk, port=INTER_MASTER_PORT)

    def flush(self):
        self.contenders = {}

    def handle_sub_msg(self, frames):
        envelope = Envelope.from_bytes(frames[-1])
        msg = envelope.message

        if type(msg) == SubBlockContender:
            self.recv_sub_block_contender(msg)
        elif type(msg) == MainBlock:
            self.prepare_main_block(msg)
        else:
            raise Exception("BlockManager got message type {} from SUB socket that it does not know how to handle"
                            .format(type(msg)))
        # Last frame, frames[-1] will be the envelope binary

    def recv_sub_block_contender(self, sbc: SubBlockContender):
        cached_sbc = self.contenders.get(sbc._data.inputHash)
        if not cached_sbc:
            self.contenders[sbc._data.inputHash] = {
                'result_hash': sbc._data.resultHash,
                'input_hash': sbc._data.inputHash,
                'merkle_leaves': sbc._data.merkleLeaves,
                'signatures': [sbc._data.signature],
                'transactions_count': len(sbc.merkle_leaves),
                'transactions': sbc._data.transactions,
                'transactions_received': {Hasher.hash(tx): True for tx in sbc._data.transactions}
            }
            self.log.important('Validated and stored SubBlockContender {}'.format(sbc))
        elif sbc == cached_sbc:
            self.contenders[sbc._data.inputHash]['signatures'].append(sbc._data.signature)
            for tx in sbc._data.transactions:
                self.contenders[sbc._data.inputHash]['transactions_received'][Hasher.hash(tx)] = True
            self.log.important('Received from another delegate for SubBlockContender {}'.format(sbc))
        self.prepare_main_block()

    def prepare_main_block(self):
        self.log.info('Received {}/{} ({} required) signatures and {}/{} total transactions'.format(
            len(self.contenders['signatures']), TOP_DELEGATES, NODES_REQUIRED_CONSENSUS,
            len(self.contenders['transactions_received']), self.contenders['transactions_count']
        ))
        if len(self.contenders['signatures']) >= NODES_REQUIRED_CONSENSUS and \
            len(self.contenders['transactions_received']) == self.contenders['transactions_count']:
            self.log.critical('##TODO## PREPARING BLOCK: {}'.format(self.contenders))
            # TODO MainBlock.create()...
            # send main block

    def recv_main_block(self, mb: MainBlock):
        # TODO Check input_hash
        pass
