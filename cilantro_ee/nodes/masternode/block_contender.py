from cilantro_ee.sockets.services import AsyncInbox
from collections import defaultdict
from cilantro_ee.storage import MetaDataStorage

import capnp
import os

from cilantro_ee.messages import Message, MessageType, schemas
from cilantro_ee.crypto.wallet import _verify
from cilantro_ee.containers.merkle_tree import merklize

import asyncio
import time
from copy import deepcopy
import math

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
            return

        if len(msg_blob.contenders) != self.expected_subblocks:
            return

        # Make sure all the contenders are valid
        all_valid = True
        for i in range(len(msg_blob.contenders)):
            try:
                self.sbc_is_valid(msg_blob.contenders[i], i)
            except SBCException:
                all_valid = False

        # Add the whole contender
        if all_valid:
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

            for i in range(len(expected_tree)):
                if expected_tree[i] != sbc.merkleTree.leaves[i]:
                    raise SBCMerkleLeafVerificationError

    async def receive_sbc(self):
        while len(self.q) <= 0:
            await asyncio.sleep(0)

        return self.q.pop(0)


class CurrentContenders:
    def __init__(self, total_contacts=2, quorum_ratio=0.66, expected_subblocks=4):
        self.total_contacts = total_contacts
        self.consensus = math.ceil(total_contacts * quorum_ratio)

        self.sbcs = defaultdict(lambda: defaultdict(set))

        # Number of votes for most popular SBC. Used for consensus failure checking
        self.top_votes = defaultdict(int)

        # Finished SBCs
        self.finished = {}

        # Number of different input hashes we expect to recieve
        self.expected = expected_subblocks

        self.votes_left = defaultdict(lambda: total_contacts)

    def add_sbcs(self, sbcs):
        for sbc in sbcs.contenders:
            self.votes_left[sbc.inputHash] -= 1
            result_hash = sbc.merkleTree.leaves[0]
            self.sbcs[sbc.inputHash][result_hash].add(sbc)

            # If its done, put it in the list
            if len(self.sbcs[sbc.inputHash][result_hash]) >= self.consensus:
                self.finished[sbc.subBlockNum] = sbc

            # Update the top vote for this hash
            self.top_votes[sbc.inputHash] = max(self.top_votes[sbc.inputHash], len(self.sbcs[sbc.inputHash][result_hash]))

            # Check if consensus possible
            if self.votes_left[sbc.inputHash] + self.top_votes[sbc.inputHash] < self.consensus:
                self.finished[sbc.subBlockNum] = None


class Aggregator:
    def __init__(self, socket_id, ctx, driver, expected_subblocks=4):
        self.expected_subblocks = expected_subblocks
        self.sbc_inbox = SBCInbox(
            socket_id=socket_id,
            ctx=ctx,
            driver=driver,
            expected_subblocks=self.expected_subblocks
        )

    async def gather_subblocks(self, total_contacts, quorum_ratio=0.66, expected_subblocks=4, timeout=1000):
        self.sbc_inbox.expected_subblocks = expected_subblocks
        contenders = CurrentContenders(total_contacts, expected_subblocks=expected_subblocks)
        now = time.time()
        while time.time() - now < timeout and len(contenders.finished) < contenders.expected:
            sbcs = await self.sbc_inbox.receive_sbc()
            contenders.add_sbcs(sbcs)

        subblocks = deepcopy(contenders.finished)
        del contenders
        return subblocks
