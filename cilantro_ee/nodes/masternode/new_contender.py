from cilantro_ee.messages import schemas
from cilantro_ee.nodes.masternode.sbc_inbox import SBCInbox
from cilantro_ee.logger.base import get_logger
from cilantro_ee.crypto import canonical

import asyncio
import capnp
import os
import time

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
    def __init__(self, input_hash, index, total_contacts, required_consensus=0.66, adequate_consensus=0.51):
        self.input_hash = input_hash
        self.index = index

        self.potential_solutions = {}
        self.best_solution = None

        self.total_responses = 0
        self.total_contacts = total_contacts

        self.required_consensus = required_consensus
        self.adequate_consensus = adequate_consensus

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

        self.total_responses += 1

    @property
    def failed(self):
        # True if all responses are recorded and required consensus is not possible
        return self.total_responses >= self.total_contacts and \
               not self.has_required_consensus

    @property
    def has_required_consensus(self):
        if self.best_solution is None:
            return False

        if self.best_solution.votes / self.total_contacts < self.required_consensus:
            return False

        return True

    @property
    def has_adequate_consensus(self):
        if self.best_solution is None:
            return False

        if self.best_solution.votes / self.total_contacts < self.adequate_consensus:
            return False

        return True

    @property
    def serialized_solution(self):
        if not self.has_adequate_consensus:
            return None
        if self.failed:
            return None

        return self.best_solution.struct_to_dict()


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
                s = SubBlockContender(input_hash=sbc.inputHash, index=sbc.subBlockNum, total_contacts=self.total_contacts)
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

    def block_has_consensus(self):
        for sb in self.subblock_contenders:
            if sb is None:
                return False
            if not sb.has_required_consensus:
                return False

        return True

    def get_current_best_block(self):
        block = []

        # Where None is appended = failed
        for sb in self.subblock_contenders:
            if sb is None:
                block.append(None)
            else:
                block.append(sb.serialized_solution)

        return block

    @property
    def responses(self):
        m = 0
        for sb in self.subblock_contenders:
            if sb is None:
                continue
            if sb.total_responses > m:
                m = sb.total_responses

        return m

# Can probably move this into the masternode. Move the sbc inbox there and deprecate this class
class Aggregator:
    def __init__(self, socket_id, ctx, driver, wallet, expected_subblocks=4, seconds_to_timeout=5):
        self.expected_subblocks = expected_subblocks
        self.sbc_inbox = SBCInbox(
            socket_id=socket_id,
            ctx=ctx,
            driver=driver,
            expected_subblocks=self.expected_subblocks,
            wallet=wallet
        )
        self.driver = driver

        self.seconds_to_timeout = seconds_to_timeout

        self.log = get_logger('AGG')

    async def gather_subblocks(self, total_contacts, quorum_ratio=0.66, adequate_ratio=0.5, expected_subblocks=4):
        self.sbc_inbox.expected_subblocks = expected_subblocks

        contenders = BlockContender(
            total_contacts=total_contacts,
            required_consensus=quorum_ratio,
            total_subblocks=expected_subblocks,
            acceptable_consensus=adequate_ratio
        )

        # Add timeout condition.
        started = time.time()
        while (not contenders.block_has_consensus() and contenders.responses < contenders.total_contacts) and \
                time.time() - started < self.seconds_to_timeout:

            if self.sbc_inbox.has_sbc():
                print('yes')
                sbcs = await self.sbc_inbox.receive_sbc() # Can probably make this raw sync code
                contenders.add_sbcs(sbcs)
            await asyncio.sleep(0)

        self.log.info('Done aggregating new block.')

        block = contenders.get_current_best_block()

        self.log.info(f'Best block gotten: {block}')

        return canonical.block_from_subblocks(
            block,
            previous_hash=self.driver.latest_block_hash,
            block_num=self.driver.latest_block_num + 1
        )

    async def start(self):
        asyncio.ensure_future(self.sbc_inbox.serve())

    def stop(self):
        self.sbc_inbox.stop()
