from cilantro import Constants
from cilantro.protocol.statemachine import *
from cilantro.nodes.masternode.base_state import MNBaseState
from cilantro.nodes.masternode.run_state import MNRunState
from cilantro.utils import Hasher
from cilantro.messages import BlockContender
from cilantro.protocol.structures import MerkleTree


class MNNewBlockState(MNBaseState):

    def reset_attrs(self):
        self.pending_blocks = []

    # Development sanity check (remove this in production)
    @enter_from_any
    def enter_any(self, prev_state):
        raise Exception("NewBlockState should only be entered from RunState, but previous state is {}".format(prev_state))

    @enter_from(MNRunState)
    def enter_from_run(self, prev_state, block: BlockContender):
        self.log.debug("Entering NewBlockState with block contender {}".format(block))


    @input(BlockContender)
    def handle_block_contender(self, block: BlockContender):
        if self.validate_block_contender(block):
            self.log.debug("Adding block contender {} ")
            self.pending_blocks.append(block)

    def validate_sigs(self, signatures, msg) -> bool:
        for sig in signatures:
            self.log.info("mn verifying signature: {}".format(sig))
            if not sig.verify(msg, sig.sender):
                self.log.error("!!!! Oh no why couldnt we verify sig {}???".format(sig))
                return False
        return True

    def validate_block_contender(self, block: BlockContender) -> bool:
        """
        Helper method to validate a block contender. For a block contender to be valid it must:
        1) Have a provable merkle tree, ie. all nodes must be hash of (left child + right child)
        2) Be signed by at least 2/3 of the top 32 delegates
        :param block_contender: The BlockContender to validate
        :return: True if the BlockContender is valid, false otherwise
        """
        # Development sanity checks (these should be removed in production)
        assert len(block.nodes) >= 1, "Masternode got block contender with no nodes! {}".format(block)
        assert len(block.signatures) >= Constants.Testnet.Majority, \
            "Received a block contender with only {} signatures (which is less than a majority of {}"\
            .format(len(block.signatures), Constants.Testnet.Majority)

        # Prove Merkle Tree
        hash_of_nodes = Hasher.hash_iterable(block.nodes, algorithm=Hasher.Alg.SHA3_256, return_bytes=True)
        if not MerkleTree.verify_tree(self.tx_hashes, hash_of_nodes):
            self.log.error("\n\n\n\nCOULD NOT VERIFY MERKLE TREE FOR BLOCK CONTENDER {}\n\n\n".format(block))
            return False

        # Validate signatures
        if not self.validate_sigs(block.signatures, hash_of_nodes):
            self.log.error("MN COULD NOT VALIDATE SIGNATURES FOR CONTENDER {}".format(block))
            return False

        return True