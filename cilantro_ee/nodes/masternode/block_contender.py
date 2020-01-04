from cilantro_ee.services.storage.vkbook import VKBook
from cilantro_ee.services.storage.state import MetaDataStorage
from cilantro_ee.core.logger import get_logger
from cilantro_ee.containers.merkle_tree import MerkleTree

from cilantro_ee.messages.message_type import MessageType
from cilantro_ee.messages.message import Message
from cilantro_ee.crypto import _verify

from collections import defaultdict
from typing import List
import time
import hashlib


class SBCSenderSignerMismatchError(Exception):
    pass


class SBCIndexMismatchError(Exception):
    pass


class SBCInvalidSignatureError(Exception):
    pass


class SBCTransactionNotInContenderError(Exception):
    pass


class SBCBlockHashMismatchError(Exception):
    pass


class SBCMerkleLeafVerificationError(Exception):
    pass


class SBCIndexGreaterThanPossibleError(Exception):
    pass


class SubBlockGroup:
    def __init__(self, sb_idx: int, curr_block_hash: str,
                 contacts: VKBook, subblocks_per_block: int):

        self.sb_idx, self.curr_block_hash = sb_idx, curr_block_hash
        self.log = get_logger("SBGroup[{}]".format(self.sb_idx))
        self.subblocks_per_block = subblocks_per_block

        self.rh = defaultdict(set)  # mapping of result_hash: set of SubBlockContenders

        self.transactions = {}  # tx_hash: TransactionData
        self.sender_to_sbc = {}  # map of sender_vk: SubBlockContender

        self.contacts = contacts

        self.min_quorum = self.contacts.delegate_quorum_min
        self.max_quorum = self.contacts.delegate_quorum_max

        self.best_rh = None  # The result hash with the most votes so far

    def is_consensus_possible(self) -> bool:
        num_votes = 0
        for rh in self.rh:
            votes_for_rh = len(self.rh[rh])
            if votes_for_rh >= self.max_quorum:  # Consensus reached on this sub block
                return True
            num_votes += votes_for_rh

        remaining_votes = len(self.contacts.delegates) - num_votes
        leading_rh = len(self.rh[self.best_rh])

        if leading_rh + remaining_votes < self.max_quorum:
            self.log.fatal("Consensus impossible for SB index {}!\n"
                           "consensus: {},\n"
                           "result hashes: {}".format(self.sb_idx, leading_rh, self.rh))
            return False

        return True

    def get_sb(self):
        #assert self.is_consensus_reached(), "Consensus must be reached to get a SubBlock!"

        # Paranoid dev checks
        # TODO make sure all merkle leaves are the same, and all result hashes are the same for self.rh[merkle_root],
        # all sb_idx matches ours, all input hashes are the same

        merkle_root = self.best_rh
        contenders = self.rh[merkle_root]

        sigs = [c.signature for c in contenders]

        # Get a contender from the set. This presumes that the contenders have identical data, which they should.
        # contenders should be grouped based on prevBlockHash and resultHash equality - then they will have identical data - raghu
        contender = contenders.pop()
        contenders.add(contender)

        leaves = contender.merkleLeaves
        input_hash = contender.inputHash

        txs = self._get_ordered_transactions()
        transactions = [Message.unpack_message_internal(MessageType.TRANSACTION_DATA, tx) for tx in txs]

        # looks like sbc has txns packed while sb will have them as unpacked. Need to eliminate these inconsistencies for better performance - raghu
        _, sb = Message.get_message(
                   MessageType.SUBBLOCK, merkleRoot=merkle_root,
                   signatures=sigs, merkleLeaves=[leaf for leaf in leaves],
                   subBlockNum=self.sb_idx, inputHash=input_hash,
                   transactions=transactions)
   
        return sb

    def is_consensus_reached(self) -> bool:
        cons_reached = len(self.rh[self.best_rh]) >= self.max_quorum

        return cons_reached

    def get_current_quorum_reached(self) -> int:
        # If the best result is still less than the minimum required quorum, return zero
        if len(self.rh[self.best_rh]) < self.min_quorum:
            return 0

        # If the best result is more than the max quorum, return the max quorum
        if len(self.rh[self.best_rh]) >= self.max_quorum:
            return self.max_quorum

        # Otherwise, calculate the total number of votes recieved at this point in time
        num_votes = 0

        for rh in self.rh:
            votes_for_rh = len(self.rh[rh])
            num_votes += votes_for_rh

        # Get the number of votes of the most popular result
        leading_rh = len(self.rh[self.best_rh])

        # The quorum is reduced if the most popular result is 90% of the current votes
        is_reduced_quorum = leading_rh >= (9 * num_votes // 10)

        # If this is the case, return the number for the most popular votes
        return leading_rh if is_reduced_quorum else 0

    def get_input_hashes(self) -> list:
        s = set()

        for sbc in self.sender_to_sbc.values():
            s.add(sbc.inputHash)

        return list(s)

    def is_empty(self):
        return len(self._get_merkle_leaves()) == 0

    def _get_merkle_leaves(self) -> list:
        if self.best_rh is None:
            return []

        # All merkle leaves should be the same, so just chose any contender from the set
        return next(iter(self.rh[self.best_rh])).merkleLeaves

    def _get_ordered_transactions(self):
        #assert self.is_consensus_reached(), "Must be in consensus to get ordered transactions"  # TODO remove

        # ... Doesn't this return tx's for ALL SBC? WTF IS GOING ON HERE....
        # return [self.transactions[tx_hash] for tx_hash in self._get_merkle_leaves()]
        return next(iter(self.rh[self.best_rh])).transactions

    def add_sbc(self, sender_vk: bytes, sbc):
        # Verify that the SubBlockContender message is validly constructured
        if not self._verify_sbc(sender_vk, sbc):
            self.log.error("Could not verify SBC from sender {}".format(sender_vk))
            return

        # If a sender 'resubmits' a SubBlockContender, it overwrites the previous. Seems like a potential attack vector?
        if sender_vk in self.sender_to_sbc:
            self.log.debug("Sender {} has already submitted a contender for sb idx {} with prev hash {}! Removing his "
                           "old contender before adding a new one".format(sender_vk, self.sb_idx, self.curr_block_hash))
            existing_sbc = self.sender_to_sbc[sender_vk]
            self.rh[existing_sbc.resultHash].remove(existing_sbc)

        # Add the SBC to the mapping of entries between SBCs and senders. This can be a set instead
        self.sender_to_sbc[sender_vk] = sbc

        # Add the SBC to the result hash. Shouldn't we hash it ourselves and just keep a hashmap?
        # Also, wouldn't it be easier to have a counter?
        self.rh[sbc.resultHash].add(sbc)

        # If the new subblock is now the 'best result', set it so in the instance.
        if (self.best_rh is None) or (len(self.rh[sbc.resultHash]) > len(self.rh[self.best_rh])):
            self.best_rh = sbc.resultHash

        # Not sure what this is doing
        for tx in sbc.transactions:

            h = hashlib.sha3_256()
            h.update(tx)
            _hash = h.digest()

            if _hash not in self.transactions:
                self.transactions[_hash] = tx

        self.log.info("Added SBC")

    def _verify_sbc(self, sender_vk: bytes, sbc) -> bool:
        # Dev sanity checks
        merkle_proof = Message.unpack_message_internal(MessageType.MERKLE_PROOF, sbc.signature)

        if not merkle_proof.signer == sender_vk:
            self.log.error('{} != {}'.format(merkle_proof.signer, sender_vk))
            return False

        if sbc.subBlockNum != self.sb_idx:
            self.log.error('{} != {}'.format(sbc.subBlockNum, self.sb_idx))
            return False

        # TODO move this validation to the SubBlockCotender objects instead
        # Validate signature

        valid_sig = _verify(vk=merkle_proof.signer,
                            msg=merkle_proof.hash,
                            signature=merkle_proof.signature)

        if not valid_sig:
            #self.log.error('SubBlockContender does not have a valid signature! SBC: {}'.format(sbc))
            return False

        # TODO move this validation to the SubBlockCotender objects instead
        # Validate sbc prev block hash matches our current block hash
        if sbc.prevBlockHash != self.curr_block_hash:
            self.log.error("SBC prev block hash {} does not match our current block hash {}!\nSBC: {}"
                           .format(sbc.prevBlockHash, self.curr_block_hash, sbc))
            # raghu todo - need to fix this
            return False

        # TODO move this validation to the SubBlockCotender objects instead
        # Validate merkle leaves
        if len(sbc.merkleLeaves) > 0:
            if not MerkleTree.verify_tree_from_bytes(leaves=sbc.merkleLeaves, root=sbc.resultHash):
                self.log.error("Could not verify MerkleTree for SBC {}!".format(sbc))
                return False

        # TODO move this validation to the SubBlockCotender objects instead
        # Validate transactions
        for tx in sbc.transactions:

            h = hashlib.sha3_256()
            h.update(tx)
            _hash = h.digest()

            if _hash not in sbc.merkleLeaves:
                self.log.error('Received malicious txs that does not match merkle leaves!\nSBC: {}'.format(sbc))
                return False

        # TODO move this validation to the SubBlockCotender objects instead
        # Validate sub block index is in range
        # can't use it as it is. need to convert back to the index
        # if sbc.subBlockNum >= self.subblocks_per_block:
            # self.log.error("Got SBC with out of range sb_index {}!\nSBC: {}".format(sbc.subBlockNum, sbc))
            # return False

        return True


class BlockContender:
    def __init__(self, subblocks_per_block, builders_per_block, contacts):
        self.log = get_logger("BlockContender")
        self.committed = False
        self.consensus_reached = False

        self.state = MetaDataStorage()
        self.curr_block_hash = self.state.get_latest_block_hash()

        self.time_created = time.time()

        self.sb_groups = {}  # Mapping of sb indices to SubBlockGroup objects
        self.old_input_hashes = set()  # A set of input hashes from the last block.

        self.subblocks_per_block = subblocks_per_block
        self.builders_per_block = builders_per_block

        self.contacts = contacts

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
        self.curr_block_hash = self.state.get_latest_block_hash()
        self.time_created = time.time()
        self.sb_groups = {}  # Mapping of sb indices to SubBlockGroup objects
        self.log.info("BlockContender reset with curr_block_hash={}".format(self.curr_block_hash))

    def is_consensus_reached(self) -> bool:
        assert len(self.sb_groups) <= self.subblocks_per_block, "Got more sub block indices than SB_PER_BLOCK!"

        if len(self.sb_groups) != self.subblocks_per_block:
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
        if len(self.sb_groups) < self.subblocks_per_block:
            return 0

        cur_quorum = self.sb_groups[0].contacts.delegate_quorum_max
        for sb_idx, sb_group in self.sb_groups.items():
            cur_quorum = min(cur_quorum, sb_group.get_current_quorum_reached())

        return cur_quorum

    def is_empty(self):
        # assert self.is_consensus_reached(), "Consensus must be reached to check if this block is empty!"

        for sb_group in self.sb_groups.values():
            if not sb_group.is_empty():
                return False

        return True

    def get_sb_data(self):
        #assert self.is_consensus_reached(), "Cannot get block data if consensus is not reached!"
        #assert len(self.sb_groups) == self.subblocks_per_block, "More sb_groups than subblocks! sb_groups={}".format(self.sb_groups)

        # Build the sub-blocks
        sb_data = []
        for sb_group in self.sb_groups.values():
            sb_data.append(sb_group.get_sb())

        sb_data = sorted(sb_data, key=lambda sb: sb.subBlockNum)

        #assert len(sb_data) == self.subblocks_per_block, "Block has {} sub blocks but there are {} SBs/per/block" \
                                                 #.format(len(sb_data), self.subblocks_per_block)

        return sb_data

    def get_failed_block_notif(self):
        input_hashes = self._get_input_hashes()
        first_sb_idx = self._get_first_sb_idx()
        block_num = self.state.latest_block_num + 1
        last_hash = self.state.latest_block_hash
        return BlockNotification.get_failed_block_notification(
                                  block_num=block_num, prev_block_hash=last_hash,
                                  first_sb_idx=first_sb_idx, input_hashes=input_hashes)

    def add_sbc(self, sender_vk: str, sbc) -> bool:
        """
        Adds a SubBlockContender to this BlockContender's data.
        :param sender_vk: The VK of the sender of the SubBlockContender
        :param sbc: The SubBlockContender instance to add
        :return: True if this is the first SBC added to this BlockContender, and false otherwise
        """
        # Make sure this SBC does not refer to the last block created by checking the input hash
        if sbc.inputHash in self.old_input_hashes:
            self.log.info("Got SBC from prev block from sender {}! Ignoring.".format(sender_vk))  # TODO change log lvl?
            return False

        groups_empty = len(self.sb_groups) == 0

        if sbc.subBlockNum not in self.sb_groups:
            self.sb_groups[sbc.subBlockNum] = SubBlockGroup(sb_idx=sbc.subBlockNum, curr_block_hash=self.curr_block_hash, contacts=self.contacts, subblocks_per_block=self.subblocks_per_block)

        self.sb_groups[sbc.subBlockNum].add_sbc(sender_vk, sbc)
        return groups_empty

    # Return to this. Is this behaving properly? Is it redundant?
    def get_first_sb_idx_unsorted(self, sb_groups) -> int:
        sb_idx = sb_groups[0].sb_idx
        sbb_rem = sb_idx % self.builders_per_block
        # assert sb_idx >= sbb_rem, "sub block indices are not maintained properly"
        return sb_idx - sbb_rem

    def get_first_sb_idx_sorted(self) -> int:
        sb_groups = sorted(self.sb_groups.values(), key=lambda sb: sb.sb_idx)
        num_sbg = len(sb_groups)
        assert num_sbg <= self.subblocks_per_block, "Sub groups are not in a consistent state"
        return self.get_first_sb_idx_unsorted(sb_groups)

    # Pads empty sb groups?
    def get_input_hashes_sorted(self) -> List[list]:
        sb_groups = sorted(self.sb_groups.values(), key=lambda sb: sb.sb_idx)
        num_sbg = len(sb_groups)
        # assert num_sbg <= self.subblocks_per_block, "Sub groups are not in a consistent state"

        sb_idx = self.get_first_sb_idx_unsorted(sb_groups) # 0
        input_hashes = []

        for sb_group in sb_groups:
            # In what natural situation does is while loop conditional met?
            while sb_idx < sb_group.sb_idx:
                sb_idx += 1
                num_sbg += 1
                input_hashes.append([])

            input_hashes.append(sb_group.get_input_hashes())
            sb_idx += 1

        # In what natural situation does is while loop conditional met?
        while num_sbg < self.subblocks_per_block:
            num_sbg += 1
            input_hashes.append([])

        return input_hashes
