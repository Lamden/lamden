from cilantro.storage.state import StateDriver
from cilantro.logger.base import get_logger
from cilantro.protocol.structures.merkle_tree import MerkleTree
from cilantro.constants.system_config import *

from cilantro.messages.consensus.sub_block_contender import SubBlockContender
from cilantro.messages.consensus.merkle_signature import MerkleSignature
from cilantro.messages.block_data.sub_block import SubBlock

from collections import defaultdict


class BlockContender:

    def __init__(self, prev_block_hash: str):
        self.log = get_logger("BlockBuilder")
        self.prev_block_hash = prev_block_hash
        self.committed = False
        self.consensus_reached = False
        self.curr_block_hash = StateDriver.get_latest_block_hash()

        self.result_hashes = defaultdict(dict)  # Mapping of result_hash: {sender_vk: SubblockContender}
        self.transactions = {}  # tx_hash: TransactionData

    def is_consensus_reached(self) -> bool:
        if len(self.result_hashes) < NUM_SB_PER_BLOCK:
            return False

        sb_count = 0
        for result_hash in self.result_hashes:
            if len(self.result_hashes[result_hash]) >= DELEGATE_MAJORITY:
                self.log.spam("Consensus achieved on result hash {}".format(result_hash))
                sb_count += 1

        # Sanity check, it should should impossible to achieve consensus on more than sub-blocks than NUM_SB_PER_BLOCK
        assert sb_count <= NUM_SB_PER_BLOCK, "Achieved consensus on more than {} sub blocks!!! WHY THO\n" \
                                             "result_hashes={}".format(NUM_SB_PER_BLOCK, self.result_hashes)

        # TODO -- If we have consensus on the sub-blocks, make sure we have all the transactions

        self.log.debugv("Achieved consensus on {}/{} subblocks".format(sb_count, NUM_SB_PER_BLOCK))
        return sb_count == NUM_SB_PER_BLOCK

    def is_consensus_possible(self) -> bool:
        # TODO implement
        # Return true if it is still possible to get 2/3rds consensus
        return True

    def add_sbc(self, sender_vk: str, sbc: SubBlockContender):
        if not self._verify_sbc(sender_vk, sbc):
            return

        self.result_hashes[sbc.result_hash][sender_vk] = sbc

        if len(self.result_hashes) > NUM_SB_PER_BLOCK:
            self.log.warning("More than {} unique result hashes for prev block hash {}!!! Result hashes: {}"
                             .format(NUM_SB_PER_BLOCK, self.curr_block_hash, list(self.result_hashes.keys())))

        for tx in sbc.transactions:
            if tx.hash not in self.transactions:
                self.transactions[tx.hash] = tx

    def _validate_txs(self, sbc: SubBlockContender) -> bool:
        for tx in sbc.transactions:
            if tx.hash not in sbc.merkle_leaves:
                self.log.warning(
                    'Received malicious txs that does not match merkle leaves! SBC: {}'.format(sbc))
                return False

        return True

    def _verify_sbc(self, sender_vk: str, sbc: SubBlockContender) -> bool:
        # Sender VK should match the Merkle signature's signer
        assert sbc.signature.sender == sender_vk, "Merkle sig {} on SBC does not match sender {}"\
                                                  .format(sbc.signature, sender_vk)

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
                self.log.warning('Received malicious txs that does not match merkle leaves! SBC: {}'.format(sbc))
                return False

        # Check we dont have a SBC from this sender already
        if sender_vk in self.result_hashes[sbc.result_hash]:
            self.log.warning("ALERT! Already received SBC from sender {}!\nsb contender: {}\nprev_block_hash: {}"
                             .format(sender_vk, sbc, sbc.prev_block_hash))
            return False

        return True
