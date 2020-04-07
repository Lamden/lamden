import capnp
import os
from cilantro_ee.messages import schemas

subblock_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/subblock.capnp')


class PotentialSolution:
    def __init__(self, struct):
        self.struct = struct
        self.signatures = []

    @property
    def votes(self):
        return len(self.signatures)


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
    def __init__(self, total_contacts, total_subblocks, required_consensus):
        self.total_contacts = total_contacts
        self.total_subblocks = total_subblocks
        self.required_consensus = required_consensus

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

    def get_capnp_message(self):
        pass
