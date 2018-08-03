from cilantro.constants.zmq_filters import MASTERNODE_DELEGATE_FILTER
from cilantro.constants.testnet import MAJORITY
from cilantro.constants.masternode import NEW_BLOCK_TIMEOUT, FETCH_BLOCK_TIMEOUT
from cilantro.constants.nodes import BLOCK_SIZE
from cilantro.nodes.masternode import MNBaseState, Masternode

from cilantro.utils import Hasher

from cilantro.storage.blocks import List, BlockStorageDriver, BlockStorageException

from cilantro.protocol.states.decorators import enter_from_any, enter_from, input_request, input_timeout, input, timeout_after

from cilantro.messages.consensus.block_contender import BlockContender
from cilantro.messages.block_data.block_metadata import NewBlockNotification
from cilantro.messages.block_data.transaction_data import TransactionRequest, TransactionReply
from cilantro.messages.envelope.envelope import Envelope

from cilantro.protocol.structures import MerkleTree
from collections import deque
import random


MNRunState = "MNRunState"
MNNewBlockState = "MNNewBlockState"
MNFetchNewBlockState = "MNFetchNewBlockState"


@Masternode.register_state
class MNNewBlockState(MNBaseState):

    def reset_attrs(self):
        self.pending_blocks = deque()
        self.current_block = None

    @timeout_after(NEW_BLOCK_TIMEOUT)
    def timeout(self):
        # TODO i think this timeout is essentially useless b/c all the fetching/processing is done in
        # MNFetchNewBlockState. This state just orchestrates things
        self.log.critical("MN failed to publish a new block in less than {} seconds!".format(NEW_BLOCK_TIMEOUT))
        self.parent.transition(MNRunState, success=False)

    # Development sanity check (remove in production)
    @enter_from_any
    def enter_any(self, prev_state):
        raise Exception("NewBlockState should only be entered from RunState or FetchNewBlockState, but previous state is {}".format(prev_state))

    @enter_from(MNRunState)
    def enter_from_run(self, block: BlockContender):
        self.reset_attrs()
        self.log.debug("Entering NewBlockState with block contender {}".format(block))

        if self.validate_block_contender(block):
            self.current_block = block
            self.log.debug("Entering fetch state for block contender {}".format(self.current_block))
            self.parent.transition(MNFetchNewBlockState, block_contender=self.current_block)
        else:
            self.log.warning("Got invalid block contender straight from Masternode. Transitioning back to RunState /w success=False")
            self.parent.transition(MNRunState, success=False)

    @enter_from(MNFetchNewBlockState)
    def enter_from_fetch_block(self, success=False, retrieved_txs=None, pending_blocks=None):
        self.pending_blocks.extend(pending_blocks)

        if success:
            assert retrieved_txs and len(retrieved_txs) > 0, "Success is true but retrieved_txs {} is None/empty"
            self.log.info("FetchNewBlockState finished successfully. Storing new block.")
            self._new_block_procedure(block=self.current_block, txs=retrieved_txs)

            self.log.info("Done storing new block. Transitioning back to run state with success=True")
            self.parent.transition(MNRunState, success=True)
        # If failure, then try the next block contender in the queue (if any).
        else:
            self.log.warning("FetchNewBlockState failed for block {}. Trying next block (if any)".format(self.current_block))
            self._try_next_block()

    def _try_next_block(self):
        if len(self.pending_blocks) > 0:
            self.current_block = self.pending_blocks.popleft()
            self.log.debug("Entering fetch state for block contender {}".format(self.current_block))
            self.parent.transition(MNFetchNewBlockState, block_contender=self.current_block)
        else:
            self.log.warning("No more pending blocks. Transitioning back to RunState /w success=False")
            self.parent.transition(MNRunState, success=False)

    def _new_block_procedure(self, block: BlockContender, txs: List[bytes]):
        self.log.notice("Masternode attempting to store a new block")

        # Attempt to store block
        try:
            block_hash = BlockStorageDriver.store_block(block_contender=block, raw_transactions=txs, publisher_sk=self.parent.signing_key)
            self.log.important2("Masternode successfully stored new block with {} total transactiosn and block hash {}"
                                .format(len(txs), block_hash))
        except BlockStorageException as e:
            self.log.error("Error storing block!\nError = {}".format(e))
            self._try_next_block()
            return

        # Notify TESTNET_DELEGATES of new block
        self.log.info("Masternode sending NewBlockNotification to TESTNET_DELEGATES with new block hash {} ".format(block_hash))
        notif = NewBlockNotification.create(**BlockStorageDriver.get_latest_block(include_number=False))
        self.parent.composer.send_pub_msg(filter=MASTERNODE_DELEGATE_FILTER, message=notif)

    @input_request(BlockContender)
    def handle_block_contender(self, block: BlockContender):
        if self.validate_block_contender(block):
            self.pending_blocks.append(block)

    def _validate_sigs(self, block: BlockContender) -> bool:
        signatures = block.signatures
        msg = MerkleTree.hash_nodes(block.merkle_leaves)

        for sig in signatures:
            # TODO -- ensure that the sender belongs to the top delegate pool
            self.log.debug("mn verifying signature: {}".format(sig))
            if not sig.verify(msg, sig.sender):
                self.log.error("Masternode could not verify signature!!! Sig={}".format(sig))
                return False
        return True

    def validate_block_contender(self, block: BlockContender) -> bool:
        """
        Helper method to validate a block contender. For a block contender to be valid it must:
        1) Have a provable merkle tree, ie. all nodes must be hash of (left child + right child)
        2) Be signed by at least 2/3 of the top 32 TESTNET_DELEGATES
        3) Have the correct number of transactions
        :param block_contender: The BlockContender to validate
        :return: True if the BlockContender is valid, false otherwise
        """
        # Development sanity checks (these should be removed in production)
        assert len(block.merkle_leaves) >= 1, "Masternode got block contender with no nodes! {}".format(block)
        assert len(block.signatures) >= MAJORITY, \
            "Received a block contender with only {} signatures (which is less than a MAJORITY of {}"\
            .format(len(block.signatures), MAJORITY)

        assert len(block.merkle_leaves) == BLOCK_SIZE, \
            "Block contender has {} merkle leaves, but block size is {}!!!\nmerkle_leaves={}"\
            .format(len(block.merkle_leaves), BLOCK_SIZE, block.merkle_leaves)

        # TODO validate the sigs are actually from the top N TESTNET_DELEGATES
        # TODO -- ensure that this block contender's previous block is this Masternode's current block...

        return block.validate_signatures()


@Masternode.register_state
class MNFetchNewBlockState(MNNewBlockState):

    # Enum to describe TESTNET_DELEGATES we are requesting block data from. A delegate who has no pending requests is in
    # NODE_AVAILABLE state. Once a request is sent to a delegate we set it to NODE_AWAITING. If the request times out,
    # we set the timed out node to NODE_TIMEOUT
    NODE_AVAILABLE, NODE_AWAITING, NODE_TIMEOUT = range(3)

    def reset_attrs(self):
        super().reset_attrs()
        self.block_contender = None
        self.node_states = {}
        self.tx_hashes = []
        self.retrieved_txs = {}

    @timeout_after(FETCH_BLOCK_TIMEOUT)
    def timeout(self):
        self.log.critical("MN failed to fetch block data in less than {} seconds!\nBlock Contender = {}"
                          .format(NEW_BLOCK_TIMEOUT, self.block_contender))
        self.parent.transition(MNNewBlockState, success=False, pending_blocks=self.pending_blocks)

    # Development sanity check (remove in production)
    @enter_from_any
    def enter_any(self, prev_state):
        raise Exception("MNFetchBlockState non-specific entry handler from state {} called! Uh oh!".format(prev_state))

    @enter_from(MNNewBlockState)
    def enter_from_new_block(self, prev_state, block_contender: BlockContender):
        self.reset_attrs()
        self.log.debug("Fetching block data for contender {}".format(block_contender))

        self.block_contender = block_contender
        self.tx_hashes = block_contender.merkle_leaves

        # Populate self.node_states TESTNET_DELEGATES who signed this block
        for sig in block_contender.signatures:
            self.node_states[sig.sender] = self.NODE_AVAILABLE

        repliers = list(self.node_states.keys())

        # Compute batch size. We take max incase the block size is smaller than the # of TESTNET_DELEGATES.
        batch_size = max(1, len(self.tx_hashes) // len(self.node_states))

        # Request individual block data from TESTNET_DELEGATES
        for i in range(len(self.node_states)):
            start_idx = i * batch_size
            end_idx = (i+1) * batch_size

            req_hashes = self.tx_hashes[start_idx:end_idx]
            vk = repliers[i % len(repliers)]

            self._request_from_delegate(req_hashes, vk)

    def _request_from_delegate(self, tx_hashes: List[str], delegate_vk: str=''):
        """
        Helper method to request a transaction from a delegate via the transactions hash.
        :param tx_hash:  The hash of the transaction to request
        :param delegate_vk:  The verifying key of the delegate to request. If not specified,
        self._first_available_node() is used
        """
        if delegate_vk:
            assert delegate_vk in self.node_states, "Expected to request from a delegate state that known in node_states"
        else:
            delegate_vk = self._first_available_node()

        self.log.debugv("Requesting {} tx hashes from VK {}".format(len(tx_hashes), delegate_vk))

        req = TransactionRequest.create(tx_hashes)
        self.parent.composer.send_request_msg(message=req, timeout=5, vk=delegate_vk)

        self.node_states[delegate_vk] = self.NODE_AWAITING

    def _first_available_node(self) -> str:
        """
        Get the first available node to request block information from. The first available node will be the first node
        that is in state NODE_AVAILABLE, or otherwise a random node with state NODE_AWAITING. If all nodes are in
        NODE_TIMEOUT state, then this method returns None
        :return: The verifying key of the first available node, as a str. If no available node exist, returns None.
        """
        awaiting_node = None
        awaiting_node_count = 0

        for node, state in self.node_states.items():
            if state == self.NODE_AVAILABLE:
                return node
            elif state == self.NODE_AWAITING:
                # Set this node as awaiting_node with probability 1/awaiting_node_count. This efficiently allows us to
                # uniformly select an awaiting node from a stream (i.e. with EXACTLY ONE iteration of self.node_states)
                awaiting_node_count += 1
                if random.random() <= 1/awaiting_node_count:
                    awaiting_node = node

        return awaiting_node  # this will intentionally be None if no NODE_AWAITING nodes are found

    @input(TransactionReply)
    def handle_tx_request(self, reply: TransactionReply):
        self.log.debug("Masternode got block data reply: {}".format(reply))

        for tx in reply.raw_transactions:
            tx_hash = Hasher.hash(tx)
            if tx_hash in self.tx_hashes:
                self.retrieved_txs[tx_hash] = tx
            else:
                self.log.error("Received block data reply with tx hash {} that is not in tx_hashes")
                return

        if len(self.retrieved_txs) == len(self.tx_hashes):
            self.log.debug("Done collecting block data. Transitioning back to NewBlockState.")
            self.parent.transition(MNNewBlockState, success=True, retrieved_txs=self._get_ordered_raw_txs(),
                                   pending_blocks=self.pending_blocks)
            return
        else:
            self.log.debug("Still {} transactions yet to request until we can build the block"
                           .format(len(self.tx_hashes) - len(self.retrieved_txs)))

    def _get_ordered_raw_txs(self) -> List[bytes]:
        assert len(self.retrieved_txs) == len(self.tx_hashes), \
            "Cannot order transactions when length of retreived txs {} != length of tx hashes {}"\
            .format(len(self.retrieved_txs), len(self.tx))

        return [self.retrieved_txs[tx_hash] for tx_hash in self.tx_hashes]

    @input_timeout(TransactionRequest)
    def handle_tx_request_timeout(self, request: TransactionRequest, envelope: Envelope):
        self.log.warning("TransactionRequest timed out for envelope with request data")
        self.log.debug("Envelope Data: {}".format(envelope))

        # TODO -- implement a way to get the VK of the dude we originally requested from
        # TODO also it appears timeouts are not working....need to fix integration tests on this and see whatsup
