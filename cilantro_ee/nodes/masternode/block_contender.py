from cilantro_ee.sockets.services import AsyncInbox
from collections import defaultdict
from cilantro_ee.storage import MetaDataStorage

import capnp
import os

from cilantro_ee.messages import Message, MessageType, schemas
from cilantro_ee.crypto.wallet import _verify
from cilantro_ee.containers.merkle_tree import verify_merkle_tree, merklize

import asyncio
import hashlib
import time
from copy import deepcopy

subblock_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/subblock.capnp')


class SBCException(Exception):
    pass


class SBCBadMessage(SBCException):
    pass


class SBCInvalidSignatureError(SBCException):
    pass


class SBCBlockHashMismatchError(SBCException):
    pass


class SBCMerkleLeafVerificationError(SBCException):
    pass


class SBCIndexMismatchError(SBCException):
    pass


class SBCIndexGreaterThanPossibleError(SBCException):
    pass


class SBCInbox(AsyncInbox):
    def __init__(self, driver: MetaDataStorage, expected_subblocks=4, *args, **kwargs):
        self.q = []
        self.driver = driver
        self.expected_subblocks = expected_subblocks
        super().__init__(*args, **kwargs)

    def handle_msg(self, _id, msg):
        msg_type, msg_blob, _, _, _ = Message.unpack_message_2(msg)

        # Ignore bad message types
        if msg_type != MessageType.SUBBLOCK_CONTENDERS:
            raise SBCBadMessage

        if len(msg_blob.contenders) != self.expected_subblocks:
            pass

        # Make sure all the contenders are valid
        for i in range(len(msg_blob.contenders)):
            try:
                self.sbc_is_valid(msg_blob.contenders[i], i)
            except SBCException:
                pass

        # Add the whole contender
        self.q.append(msg_blob.contenders)

    def sbc_is_valid(self, sbc, sb_idx=0):
        if sbc.subBlockNum != sb_idx:
            raise SBCIndexMismatchError

        # Make sure signer is in the delegates
        valid_sig = _verify(
            vk=sbc.signer,
            msg=sbc.merkleTree.leaves[0],
            signature=sbc.merkleTree.signature
        )

        if not valid_sig:
            raise SBCInvalidSignatureError

        if sbc.prevBlockHash != self.driver.latest_block_hash:
            raise SBCBlockHashMismatchError

        # idk
        if len(sbc.merkleTree.leaves) > 0:
            txs = [tx.copy().to_bytes_packed() for tx in sbc.transactions]
            expected_tree = merklize(txs)

            print(expected_tree)
            print(sbc.merkleTree.leaves)

            for i in range(len(expected_tree)):
                if expected_tree[i] != sbc.merkleTree.leaves[i]:
                    raise SBCMerkleLeafVerificationError

    async def receive_sbc(self):
        while len(self.q) <= 0:
            await asyncio.sleep(0)

        return self.q.pop(0)


class CurrentContenders:
    def __init__(self, max_quorum=1, expected_subblocks=4):
        self.max_quorum = max_quorum
        self.sbcs = defaultdict(lambda: defaultdict(set))

        # Number of SBCs recieved for an input hash
        self.received = defaultdict(int)

        # Number of votes for most popular SBC. Used for consensus failure checking
        self.top_votes = defaultdict(int)

        # Finished SBCs
        self.finished = set()

        # Number of different input hashes we expect to recieve
        self.expected = expected_subblocks

    def add_sbc(self, sbc):
        result_hash = sbc.merkleTree.leaves[0]
        self.sbcs[sbc.inputHash][result_hash].add(sbc)
        self.received[sbc.inputHash] += 1

        # If its done, put it in the list
        if len(self.sbcs[sbc.inputHash][result_hash]) >= self.max_quorum:
            self.finished.add(sbc)

        # Update the top vote for this hash
        self.top_votes[sbc.inputHash] = max(self.top_votes[sbc.inputHash], len(self.sbcs[sbc.inputHash][result_hash]))

        # Check if consensus possible
        if self.received[sbc.inputHash] + (self.max_quorum - self.received[sbc.inputHash]) < self.max_quorum:
            pass


class Aggregator:
    def __init__(self):
        self.sbc_inbox = SBCInbox()

    async def gather_subblocks(self, quorum, expected_subblocks=4, timeout=1000):
        contenders = CurrentContenders(quorum, expected_subblocks)
        now = time.time()
        while time.time() - now < timeout and len(contenders.finished) < contenders.expected:
            sbc = await self.sbc_inbox.receive_sbc()
            contenders.add_sbc(sbc)

        subblocks = deepcopy(contenders.finished)
        del contenders
        return subblocks


# struct SubBlockContender {
#     inputHash @0 :Data;
#     transactions @1: List(T.TransactionData);
#     merkleTree @2 :MerkleTree;
#     signer @3 :Data;
#     subBlockNum @4: UInt8;
#     prevBlockHash @5: Data;
# }