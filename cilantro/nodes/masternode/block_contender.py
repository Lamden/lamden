from cilantro.storage.state import StateDriver
from cilantro.logger.base import get_logger
from cilantro.protocol.structures.merkle_tree import MerkleTree
from cilantro.constants.system_config import *

from cilantro.messages.consensus.sub_block_contender import SubBlockContender
from cilantro.messages.transaction.data import TransactionData
from cilantro.messages.consensus.merkle_signature import MerkleSignature
from cilantro.messages.block_data.sub_block import SubBlock

from collections import defaultdict
import time


class SubBlockGroup:
    
    def __init__(self, sb_idx: int, curr_block_hash: str):
        self.sb_idx, self.curr_block_hash = sb_idx, curr_block_hash
        self.log = get_logger("SBGroup[{}]".format(self.sb_idx))

        self.all_senders = set()  # set of sender VKs
        self.rh = defaultdict(set)  # mapping of result_hash: set of SubBlockContenders
        self.transactions = {}  # tx_hash: TransactionData

        self.best_rh = None  # The result hash with the most votes so far

    def is_consensus_possible(self) -> bool:
        num_votes = 0
        for rh in self.rh:
            votes_for_rh = len(self.rh[rh])
            if votes_for_rh >= DELEGATE_MAJORITY:  # Consensus reached on this block
                return True
            num_votes += votes_for_rh

        if num_votes >= DELEGATE_MAJORITY:
            self.log.fatal("Consensus impossible for SB index {}!\nresult hashes: {}".format(self.sb_idx, self.rh))
            return False

    def is_consensus_reached(self) -> bool:
        cons_reached = len(self.rh[self.best_rh]) >= DELEGATE_MAJORITY
        # for rh in self.rh:
        #     votes_for_rh = len(self.rh[rh])
        #     if votes_for_rh >= DELEGATE_MAJORITY:
        #         cons_reached = True
        #         break

        # Also make sure we have all the transactions for the sub block
        if cons_reached:
            for leaf in self.rh[0].merkle_leaves:
                if leaf not in self.transactions:
                    self.log.warning("Consensus reached for sb idx {}, but still missing tx with hash {}!".format(self.sb_idx, leaf))
                    return False

        return cons_reached

    def get_ordered_transactions(self):
        assert self.is_consensus_reached(), "Must be in consensus to get ordered transactions"
        return [self.transactions[tx_hash] for tx_hash in self.rh[0].merkle_leaves]

    def add_sbc(self, sender_vk: str, sbc: SubBlockContender):
        if not self._verify_sbc(sender_vk, sbc):
            self.log.warning("Could not verify SBC from sender {}".format(sender_vk))
            return

        self.all_senders.add(sender_vk)
        self.rh[sbc.result_hash].add(sbc)
        if (self.best_rh is None) or (len(self.rh[sbc.result_hash]) > len(self.rh[self.best_rh])):
            self.best_rh = sbc.result_hash

        if len(self.rh) > NUM_SB_PER_BLOCK:
            self.log.warning("More than {} unique result hashes for prev block hash {}!!! Result hashes: {}"
                             .format(NUM_SB_PER_BLOCK, self.curr_block_hash, list(self.rh.keys())))

        for tx in sbc.transactions:
            if tx.hash not in self.transactions:
                self.transactions[tx.hash] = tx

        self.log.info("Added SBC from sender {} with sb_index {} and result hash {}"
                      .format(sender_vk, sbc.sb_index, sbc.result_hash))

    def _verify_sbc(self, sender_vk: str, sbc: SubBlockContender) -> bool:
        # Dev sanity checks
        assert sbc.signature.sender == sender_vk, "Merkle sig {} on SBC does not match sender {}\nSBC: {}" \
                                                  .format(sbc.signature, sender_vk, sbc)
        assert sbc.sb_index == self.sb_idx, "Tried to add sb to wrong group! Group index: {}\nSBC: {}"\
                                            .format(self.sb_idx, sbc)

        # TODO move this validation to the SubBlockCotender objects instead
        # Validate signature
        if not sbc.signature.verify(bytes.fromhex(sbc.result_hash)):
            self.log.warning('SubBlockContender does not have a valid signature! SBC: {}'.format(sbc))
            return False

        # TODO move this validation to the SubBlockCotender objects instead
        # Validate sbc prev block hash matches our current block hash
        if sbc.prev_block_hash != self.curr_block_hash:
            self.log.warning("SBC prev block hash {} does not match our current block hash {}!\nSBC: {}"
                             .format(sbc.prev_block_hash, self.curr_block_hash, sbc))
            return False

        # TODO move this validation to the SubBlockCotender objects instead
        # Validate merkle leaves
        if len(sbc.merkle_leaves) > 0:
            if not MerkleTree.verify_tree_from_str(sbc.merkle_leaves, root=sbc.result_hash) or not self._validate_txs(sbc):
                self.log.warning("Could not verify MerkleTree for SBC {}!".format(sbc))
                return False

        # TODO move this validation to the SubBlockCotender objects instead
        # Validate transactions
        for tx in sbc.transactions:
            if tx.hash not in sbc.merkle_leaves:
                self.log.warning('Received malicious txs that does not match merkle leaves!\nSBC: {}'.format(sbc))
                return False

        # TODO move this validation to the SubBlockCotender objects instead
        # Validate sub block index is in range
        if sbc.sb_index <= NUM_SB_PER_BLOCK:
            self.log.warning("Got SBC with out of range sb_index {}!\nSBC: {}".format(sbc.sb_index, sbc))
            return False

        # Check we dont have a SBC from this sender already
        if sender_vk in self.all_senders:
            self.log.warning("ALERT! Already received SBC from sender {} for sb idx {}!\nSBC: {}"
                             .format(sender_vk, sbc.sb_index, sbc))
            return False

        return True


class BlockContender:

    def __init__(self):
        self.log = get_logger("BlockContender")
        self.committed = False
        self.consensus_reached = False
        self.curr_block_hash = StateDriver.get_latest_block_hash()
        self.time_created = time.time()
        self.sb_groups = {}  # Mapping of sb indices to SubBlockGroup objects

        self.log.debug("BlockContender created with curr_block_hash={}".format(self.curr_block_hash))

    def is_consensus_reached(self) -> bool:
        assert len(self.sb_groups) <= NUM_SB_PER_BLOCK, "Got more sub block indices than SB_PER_BLOCK!"

        if len(self.sb_groups) != NUM_SB_PER_BLOCK:
            return False

        for sb_idx, sb_group in self.sb_groups.items():
            if not sb_group.is_consensus_reached():
                self.log.debugv("Consensus not reached yet on sb idx {}".format(sb_idx))
                return False

        return True

    def is_consensus_possible(self) -> bool:
        """
        If any of the sub block indices have more than DELEGATE_MAJORITY contenders submitted, but no single result hash
        for that sub block index has DELEGATE_MAJORITY contenders, we can deduce it is impossible to achieve consensus
        on that sub block index (and consequently impossible to achieve consensus on the block overall)
        """
        for sb_idx, sb_group in self.sb_groups.items():
            if not sb_group.is_consensus_possible():
                return False

        return True

    def add_sbc(self, sender_vk: str, sbc: SubBlockContender):
        if sbc.sb_index not in self.sb_groups:
            self.sb_groups[sbc.sb_index] = SubBlockGroup(sb_idx=sbc.sb_index, curr_block_hash=self.curr_block_hash)

        self.sb_groups[sbc.sbc.sb_index].add_sbc(sender_vk, sbc)

