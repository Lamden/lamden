from cilantro_ee.messages import schemas
from cilantro_ee.nodes.masternode.sbc_inbox import SBCInbox
from cilantro_ee.logger.base import get_logger
from cilantro_ee.crypto import canonical

import asyncio
import capnp
import os

subblock_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/subblock.capnp')


class PotentialSolution:
    def __init__(self, struct):
        self.struct = struct
        self.signatures = []

    @property
    def votes(self):
        return len(self.signatures)

    def struct_to_dict(self):
        subblock = {
            'inputHash': self.struct.inputHash,
            'transactions': [tx.to_dict() for tx in self.struct.transactions],
            'merkleLeaves': [leaf for leaf in self.struct.merkleTree.leaves],
            'subBlockNum': self.struct.subBlockNum,
            'prevBlockHash': self.struct.prevBlockHash,
            'signatures': []
        }

        for sig in self.signatures:
            subblock['signatures'].append({
                'signature': sig[0],
                'signer': sig[1]
            })

        subblock['signatures'].sort(key=lambda i: i['signer'])

        return subblock


class SubBlockContender:
    def __init__(self, input_hash, index):
        self.input_hash = input_hash
        self.index = index

        self.potential_solutions = {}
        self.best_solution = None

    def add_potential_solution(self, sbc):
        result_hash = sbc.merkleTree.leaves[0]

        # Create a new potential solution if it is a new result hash
        if self.potential_solutions.get(result_hash) is None:
            self.potential_solutions[result_hash] = PotentialSolution(struct=sbc)

        # Add the signature to the potential solution
        p = self.potential_solutions.get(result_hash)
        p.signatures.append((sbc.merkleTree.signature, sbc.signer))

        # Update the best solution if the current potential solution now has more votes
        if self.best_solution is None or p.votes > self.best_solution.votes:
            self.best_solution = p


class BlockContender:
    def __init__(self, total_contacts, total_subblocks, required_consensus=0.66, acceptable_consensus=0.5):
        self.total_contacts = total_contacts
        self.total_subblocks = total_subblocks

        self.required_consensus = required_consensus

        # Acceptable consensus forces a block to complete. Anything below this will fail.
        self.acceptable_consensus = acceptable_consensus

        # Create an empty list to store the contenders as they come in
        self.subblock_contenders = [None for _ in range(self.total_subblocks)]

    def add_sbcs(self, sbcs):
        for sbc in sbcs:
            # If it's out of range, ignore
            if sbc.subBlockNum > self.total_subblocks - 1:
                continue

            # If it's the first contender, create a new object and store it
            if self.subblock_contenders[sbc.subBlockNum] is None:
                s = SubBlockContender(input_hash=sbc.inputHash, index=sbc.subBlockNum)
                self.subblock_contenders[sbc.subBlockNum] = s

            # Access the object at the SB index and add a potential solution
            s = self.subblock_contenders[sbc.subBlockNum]
            s.add_potential_solution(sbc)

    def current_responded_sbcs(self):
        i = 0
        for s in self.subblock_contenders:
            if s is not None:
                i += 1

        return i

    def subblock_has_consensus(self, i):
        s = self.subblock_contenders[i]

        if s is None:
            return False

        # Untestable, but also impossible. Here for sanity.
        if s.best_solution is None:
            return False

        if s.best_solution.votes / self.total_contacts < self.required_consensus:
            return False

        return True

    def block_has_consensus(self):
        for i in range(self.total_subblocks):
            if self.subblock_contenders[i] is None:
                return False

            if not self.subblock_has_consensus(i):
                return False

        return True

    def get_current_best_block(self):
        block = []

        # Where None is appended = failed
        for i in range(self.total_subblocks):
            sb = self.subblock_contenders[i]
            if sb is None:
                block.append(None)
            elif sb.best_solution is None:
                block.append(None)
            elif sb.best_solution.votes / self.total_contacts > self.acceptable_consensus:
                block.append(sb.best_solution.struct_to_dict())
            else:
                block.append(None)

        return block

# Can probably move this into the masternode. Move the sbc inbox there and deprecate this class
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

        contenders = BlockContender(
            total_contacts=total_contacts,
            required_consensus=quorum_ratio,
            total_subblocks=expected_subblocks
        )

        # Add timeout condition.
        while not contenders.block_has_consensus():
            if self.sbc_inbox.has_sbc():
                sbcs = await self.sbc_inbox.receive_sbc() # Can probably make this raw sync code
                contenders.add_sbcs(sbcs)
            await asyncio.sleep(0)

        self.log.info('Done aggregating new block.')

        block = contenders.get_current_best_block()

        return canonical.block_from_subblocks(
            block,
            previous_hash=self.driver.latest_block_hash,
            block_num=self.driver.latest_block_num + 1
        )

    async def start(self):
        asyncio.ensure_future(self.sbc_inbox.serve())

    def stop(self):
        self.sbc_inbox.stop()
