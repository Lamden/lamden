from cilantro_ee.nodes.masternode.sbc_inbox import SBCInbox
from collections import defaultdict

import capnp
import os

from cilantro_ee.crypto import canonical
from cilantro_ee.messages import schemas

import asyncio
import time
from copy import deepcopy
import math

from cilantro_ee.logger.base import get_logger

subblock_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/subblock.capnp')


class ContenderSet:
    def __init__(self):
        pass


class SubBlockContender:
    def __init__(self, input_hash, transactions):
        self.input_hash = input_hash
        self.transactions = transactions


class CurrentContenders:
    def __init__(self, total_contacts=2, quorum_ratio=0.66, expected_subblocks=4):
        self.total_contacts = total_contacts
        self.consensus = math.ceil(total_contacts * quorum_ratio)

        self.sbcs = defaultdict(lambda: defaultdict(set))
        self.signatures = defaultdict(lambda: defaultdict(set))

        # Number of votes for most popular SBC. Used for consensus failure checking
        self.top_votes = defaultdict(int)

        # Finished SBCs
        self.finished = {}

        # Number of different input hashes we expect to recieve
        self.expected = expected_subblocks

        self.votes_left = defaultdict(lambda: total_contacts)

        self.log = get_logger('CON')

    # Should be dict. push Capnp away from protocol as much as possible
    def add_sbcs(self, sbcs):
        for sbc in sbcs:
            self.votes_left[sbc.inputHash] -= 1
            result_hash = sbc.merkleTree.leaves[0]

            self.sbcs[sbc.inputHash][result_hash].add(sbc)
            self.signatures[sbc.inputHash][result_hash].add((sbc.merkleTree.signature, sbc.signer))

            # If its done, put it in the list
            if len(self.sbcs[sbc.inputHash][result_hash]) >= self.consensus:
                self.finished[sbc.subBlockNum] = self.subblock_for_sbc_and_sigs(
                    sbcs=self.sbcs[sbc.inputHash][result_hash],
                    signatures=self.signatures[sbc.inputHash][result_hash]
                )

            # Update the top vote for this hash
            self.top_votes[sbc.inputHash] = max(self.top_votes[sbc.inputHash], len(self.sbcs[sbc.inputHash][result_hash]))

            # Check if consensus possible
            if self.votes_left[sbc.inputHash] + self.top_votes[sbc.inputHash] < self.consensus:
                self.finished[sbc.subBlockNum] = None

    def subblock_for_sbc_and_sigs(self, sbcs, signatures):
        sbc = sbcs.pop()
        sbcs.add(sbc)

        subblock = {
            'inputHash': sbc.inputHash,
            'transactions': [tx.to_dict() for tx in sbc.transactions],
            'merkleLeaves': [leaf for leaf in sbc.merkleTree.leaves],
            'subBlockNum': sbc.subBlockNum,
            'prevBlockHash': sbc.prevBlockHash,
            'signatures': []
        }

        for sig in signatures:
            subblock['signatures'].append({
                'signature': sig[0],
                'signer': sig[1]
            })

        subblock['signatures'].sort(key=lambda i: i['signer'])

        return subblock


def now_in_ms():
    return int(time.time() * 1000)


class Aggregator:
    def __init__(self, socket_id, ctx, driver, wallet, expected_subblocks=4):
        self.expected_subblocks = expected_subblocks
        self.sbc_inbox = SBCInbox(
            socket_id=socket_id,
            ctx=ctx,
            driver=driver,
            expected_subblocks=self.expected_subblocks,
            wallet=wallet
        )
        self.driver = driver
        self.log = get_logger('AGG')

    async def gather_subblocks(self, total_contacts, quorum_ratio=0.66, expected_subblocks=4, timeout=5000):
        self.sbc_inbox.expected_subblocks = expected_subblocks

        contenders = CurrentContenders(total_contacts, quorum_ratio=quorum_ratio, expected_subblocks=expected_subblocks)

        while len(contenders.finished) < expected_subblocks:
            if self.sbc_inbox.has_sbc():
                sbcs = await self.sbc_inbox.receive_sbc() # Can probably make this raw sync code
                contenders.add_sbcs(sbcs)
            await asyncio.sleep(0)

        for i in range(expected_subblocks):
            if contenders.finished.get(i) is None:
                contenders.finished[i] = None

        self.log.info('Done aggregating new block.')

        subblocks = deepcopy(contenders.finished)
        del contenders

        return canonical.block_from_subblocks(
            [v for _, v in sorted(subblocks.items())],
            previous_hash=self.driver.latest_block_hash,
            block_num=self.driver.latest_block_num + 1
        )

    async def start(self):
        asyncio.ensure_future(self.sbc_inbox.serve())

    def stop(self):
        self.sbc_inbox.stop()
