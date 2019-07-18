from cilantro_ee.storage.vkbook import PhoneBook
from cilantro_ee.storage.state import MetaDataStorage
from cilantro_ee.logger.base import get_logger
from cilantro_ee.protocol.structures.merkle_tree import MerkleTree
from cilantro_ee.constants.system_config import *
from cilantro_ee.utils.hasher import Hasher

from cilantro_ee.messages.consensus.sub_block_contender import SubBlockContender
from cilantro_ee.messages.block_data.sub_block import SubBlock
from cilantro_ee.messages.block_data.notification import FailedBlockNotification

from collections import defaultdict
from typing import List
import time


class SubBlockGroup:

    def __init__(self, sb_idx: int, curr_block_hash: str):
        self.sb_idx, self.curr_block_hash = sb_idx, curr_block_hash
        self.log = get_logger("SBGroup[{}]".format(self.sb_idx))

        self.rh = defaultdict(set)  # mapping of result_hash: set of SubBlockContenders
        self.transactions = {}  # tx_hash: TransactionData
        self.sender_to_sbc = {}  # map of sender_vk: SubBlockContender
        self.min_quorum = PhoneBook.delegate_quorum_min
        self.max_quorum = PhoneBook.delegate_quorum_max
        self.best_rh = None  # The result hash with the most votes so far

    def is_consensus_possible(self) -> bool:
        num_votes = 0
        for rh in self.rh:
            votes_for_rh = len(self.rh[rh])
            if votes_for_rh >= self.max_quorum:  # Consensus reached on this sub block
                return True
            num_votes += votes_for_rh

        remaining_votes = NUM_DELEGATES - num_votes
        leading_rh = len(self.rh[self.best_rh])

        if leading_rh + remaining_votes < self.max_quorum:
            self.log.fatal("Consensus impossible for SB index {}!\n"
                           "consensus: {}, dissent: {}, quorum: {}\n"
                           "result hashes: {}".format(self.sb_idx, leading_rh, dissent, self.cur_quorum, self.rh))
            return False

        return True

    def get_sb(self) -> SubBlock:
        assert self.is_consensus_reached(), "Consensus must be reached to get a SubBlock!"

        # Paranoid dev checks
        # TODO make sure all merkle leaves are the same, and all result hashes are the same for self.rh[merkle_root],
        # all sb_idx matches ours, all input hashes are the same

        merkle_root = self.best_rh
        contenders = self.rh[merkle_root]
        c = next(iter(contenders))
        sigs = [c.signature for c in contenders]
        leaves = c.merkle_leaves
        input_hash = c.input_hash
        txs = self._get_ordered_transactions()

        sb = SubBlock.create(merkle_root=merkle_root, signatures=sigs, merkle_leaves=leaves, sub_block_idx=self.sb_idx,
                             input_hash=input_hash, transactions=txs)
        return sb

    def is_consensus_reached(self) -> bool:
        cons_reached = len(self.rh[self.best_rh]) >= self.max_quorum

        # Also make sure we have all the transactions for the sub block
        # comment out this for now as we send all transactions with a sub-block
        # if cons_reached:
            # for leaf in self._get_merkle_leaves():
                # if leaf not in self.transactions:
                    # self.log.warning("Consensus reached for sb idx {}, but still missing tx with hash {}! (and possibly"
                                     # " more)".format(self.sb_idx, leaf))
                    # return False

        return cons_reached

    def get_current_quorum_reached(self) -> int:
        if len(self.rh[self.best_rh]) < self.min_quorum:
            return 0
        if len(self.rh[self.best_rh]) >= self.max_quorum:
            return self.max_quorum
        num_votes = 0
        for rh in self.rh:
            votes_for_rh = len(self.rh[rh])
            num_votes += votes_for_rh

        leading_rh = len(self.rh[self.best_rh])
        is_reduced_quorum = leading_rh >= (9 * num_votes // 10)
        return leading_rh if is_reduced_quorum else 0

    def get_input_hashes(self) -> list:
        s = set()
        for sbc in self.sender_to_sbc.values():
            s.add(sbc.input_hash)
        return list(s)

    def is_empty(self):
        return len(self._get_merkle_leaves()) == 0

    def _get_merkle_leaves(self) -> list:
        if self.best_rh is None:
            return []

        # All merkle leaves should be the same, so just chose any contender from the set
        return next(iter(self.rh[self.best_rh])).merkle_leaves

    def _get_ordered_transactions(self):
        assert self.is_consensus_reached(), "Must be in consensus to get ordered transactions"  # TODO remove
        return [self.transactions[tx_hash] for tx_hash in self._get_merkle_leaves()]

    def add_sbc(self, sender_vk: str, sbc: SubBlockContender):
        if not self._verify_sbc(sender_vk, sbc):
            self.log.error("Could not verify SBC from sender {}".format(sender_vk))
            return

        if sender_vk in self.sender_to_sbc:
            self.log.debug("Sender {} has already submitted a contender for sb idx {} with prev hash {}! Removing his "
                           "old contender before adding a new one".format(sender_vk, self.sb_idx, self.curr_block_hash))
            existing_sbc = self.sender_to_sbc[sender_vk]
            self.rh[existing_sbc.result_hash].remove(existing_sbc)

        self.sender_to_sbc[sender_vk] = sbc
        self.rh[sbc.result_hash].add(sbc)
        if (self.best_rh is None) or (len(self.rh[sbc.result_hash]) > len(self.rh[self.best_rh])):
            self.best_rh = sbc.result_hash

        # Just a warning to help debugging
        # if len(self.rh) > 1:
        #     self.log.warning("More than {} unique result hashes for prev block hash {}!!! Result hashes: {}"
        #                      .format(1, self.curr_block_hash, list(self.rh.keys())))

        for tx in sbc.transactions:
            if tx.hash not in self.transactions:
                self.transactions[tx.hash] = tx

        self.log.info("Added SBC: {}".format(sbc))

    def _verify_sbc(self, sender_vk: str, sbc: SubBlockContender) -> bool:
        # Dev sanity checks
        assert sbc.signature.sender == sender_vk, "Merkle sig {} on SBC does not match sender {}\nSBC: {}" \
                                                  .format(sbc.signature, sender_vk, sbc)
        assert sbc.sb_index == self.sb_idx, "Tried to add sb to wrong group! Group index: {}\nSBC: {}"\
                                            .format(self.sb_idx, sbc)

        # TODO move this validation to the SubBlockCotender objects instead
        # Validate signature
        if not sbc.signature.verify(bytes.fromhex(sbc.result_hash)):
            self.log.error('SubBlockContender does not have a valid signature! SBC: {}'.format(sbc))
            return False

        # TODO move this validation to the SubBlockCotender objects instead
        # Validate sbc prev block hash matches our current block hash
        if sbc.prev_block_hash != self.curr_block_hash:
            self.log.error("SBC prev block hash {} does not match our current block hash {}!\nSBC: {}"
                           .format(sbc.prev_block_hash, self.curr_block_hash, sbc))
            return False

        # TODO move this validation to the SubBlockCotender objects instead
        # Validate merkle leaves
        if len(sbc.merkle_leaves) > 0:
            if not MerkleTree.verify_tree_from_str(sbc.merkle_leaves, root=sbc.result_hash):
                self.log.error("Could not verify MerkleTree for SBC {}!".format(sbc))
                return False

        # TODO move this validation to the SubBlockCotender objects instead
        # Validate transactions
        for tx in sbc.transactions:
            if tx.hash not in sbc.merkle_leaves:
                self.log.error('Received malicious txs that does not match merkle leaves!\nSBC: {}'.format(sbc))
                return False

        # TODO move this validation to the SubBlockCotender objects instead
        # Validate sub block index is in range
        if sbc.sb_index >= NUM_SB_PER_BLOCK:
            self.log.error("Got SBC with out of range sb_index {}!\nSBC: {}".format(sbc.sb_index, sbc))
            return False

        return True


class BlockContender:

    def __init__(self):
        self.log = get_logger("BlockContender")
        self.committed = False
        self.consensus_reached = False
        self.state = MetaDataStorage()
        self.curr_block_hash = self.state.latest_block_hash
        self.time_created = time.time()
        self.sb_groups = {}  # Mapping of sb indices to SubBlockGroup objects
        self.old_input_hashes = set()  # A set of input hashes from the last block.
        self.log.debug("BlockContender created with curr_block_hash={}".format(self.curr_block_hash))

    def reset(self):
        # Set old_input_hashes before we reset all the data
        # all_input_hashes = set()
        # for s in self._get_input_hashes():
            # all_input_hashes = all_input_hashes.union(s)
        # self.old_input_hashes = all_input_hashes
        # self.log.debugv("Old input hashes set to {}".format(self.old_input_hashes))

        # Reset all the data
        self.committed = False
        self.consensus_reached = False
        self.curr_block_hash = self.state.latest_block_hash
        self.time_created = time.time()
        self.sb_groups = {}  # Mapping of sb indices to SubBlockGroup objects
        self.log.info("BlockContender reset with curr_block_hash={}".format(self.curr_block_hash))

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
        Consensus is impossible if for any sub block contender the remaining votes were to go to the contender with the
        most votes and it still did not have 2/3 votes (i.e. contender with most votes + remaining votes < 2/3 votes)
        """
        for sb_idx, sb_group in self.sb_groups.items():
            if not sb_group.is_consensus_possible():
                return False

        return True

    def get_current_quorum_reached(self) -> int:
        if len(self.sb_groups) < NUM_SB_PER_BLOCK:
            return 0
        cur_quorum = PhoneBook.delegate_quorum_max
        for sb_idx, sb_group in self.sb_groups.items():
            cur_quorum = min(cur_quorum, sb_group.get_current_quorum_reached())

        return cur_quorum

    def is_empty(self):
        assert self.is_consensus_reached(), "Consensus must be reached to check if this block is empty!"

        for sb_group in self.sb_groups.values():
            if not sb_group.is_empty():
                return False

        return True

    def get_sb_data(self) -> List[SubBlock]:
        assert self.is_consensus_reached(), "Cannot get block data if consensus is not reached!"
        assert len(self.sb_groups) == NUM_SB_PER_BLOCK, "More sb_groups than subblocks! sb_groups={}".format(self.sb_groups)

        # Build the sub-blocks
        sb_data = []
        for sb_group in self.sb_groups.values():
            sb_data.append(sb_group.get_sb())

        sb_data = sorted(sb_data, key=lambda sb: sb.index)

        assert len(sb_data) == NUM_SB_PER_BLOCK, "Block has {} sub blocks but there are {} SBs/per/block" \
                                                 .format(len(sb_data), NUM_SB_PER_BLOCK)

        return sb_data

    def get_failed_block_notif(self) -> FailedBlockNotification:
        self.log.info("raghu 1")
        input_hashes = self._get_input_hashes()
        self.log.info("raghu 2")
        first_sb_idx = self._get_first_sb_idx()
        self.log.info("raghu 3")
        block_hash = Hasher.hash(str(input_hashes))
        self.log.info("raghu 4")
        block_num = self.state.latest_block_num + 1
        self.log.info("raghu 5")
        # sb_indices = self._get_sb_indices()
        return FailedBlockNotification.create(prev_block_hash=self.curr_block_hash, \
                                              block_hash=block_hash, block_num=block_num, \
                                              first_sb_idx=first_sb_idx, input_hashes=input_hashes)

    def add_sbc(self, sender_vk: str, sbc: SubBlockContender) -> bool:
        """
        Adds a SubBlockContender to this BlockContender's data.
        :param sender_vk: The VK of the sender of the SubBlockContender
        :param sbc: The SubBlockContender instance to add
        :return: True if this is the first SBC added to this BlockContender, and false otherwise
        """
        # Make sure this SBC does not refer to the last block created by checking the input hash
        if sbc.input_hash in self.old_input_hashes:
            self.log.info("Got SBC from prev block from sender {}! Ignoring.".format(sender_vk))  # TODO change log lvl?
            return False

        groups_empty = len(self.sb_groups) == 0
        if sbc.sb_index not in self.sb_groups:
            self.sb_groups[sbc.sb_index] = SubBlockGroup(sb_idx=sbc.sb_index, curr_block_hash=self.curr_block_hash)

        self.sb_groups[sbc.sb_index].add_sbc(sender_vk, sbc)
        return groups_empty

    def __get_first_sb_idx(self, sb_groups) -> int:
        sb_idx = sb_groups[0].sb_idx
        sbb_rem = sb_idx % NUM_SB_BUILDERS
        assert sb_idx >= sbb_rem, "sub block indices are not maintained properly"
        return sb_idx - sbb_rem

    def _get_first_sb_idx(self) -> int:
        sb_groups = sorted(self.sb_groups.values(), key=lambda sb: sb.sb_idx)
        return self.__get_first_sb_idx(sb_groups)

    def _get_input_hashes(self) -> List[list]:
        sb_groups = sorted(self.sb_groups.values(), key=lambda sb: sb.sb_idx)
        num_sbg = len(sb_groups)
        assert num_sbg <= NUM_SB_PER_BLOCK, "Sub groups are not in a consistent state"
        sb_idx = self.__get_first_sb_idx(sb_groups)
        input_hashes = []
        for sb_group in sb_groups:
            while sb_idx < sb_group.sb_idx:
                sb_idx += 1
                num_sbg += 1
                input_hashes.append([])
            input_hashes.append(sb_group.get_input_hashes())
            sb_idx += 1
        while num_sbg < NUM_SB_PER_BLOCK:
            num_sbg += 1
            input_hashes.append([])

        return input_hashes

    def _get_sb_indices(self) -> List:
        sb_groups = sorted(self.sb_groups.values(), key=lambda sb: sb.sb_idx)
        input_indices = []
        for sb_group in sb_groups:
            input_indices.append(sb_group.sb_idx)

        return input_indices
