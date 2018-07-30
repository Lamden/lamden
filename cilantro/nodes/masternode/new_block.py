from cilantro.constants.zmq_filters import masternode_delegate
from cilantro.constants.testnet import majority
from cilantro.nodes.masternode import MNBaseState, Masternode
from cilantro.storage.db import DB, insert

from cilantro.protocol.states.decorators import enter_from_any, enter_from, input_request, input_timeout, input

from cilantro.messages.consensus.block_contender import BlockContender
from cilantro.messages.consensus.new_block_notification import NewBlockNotification
from cilantro.messages.block_data.transaction_data import TransactionRequest, TransactionReply
from cilantro.messages.envelope.envelope import Envelope

# from cilantro.messages import *
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

            if len(self.pending_blocks) > 0:
                self.current_block = self.pending_blocks.popleft()
                self.log.debug("Entering fetch state for block contender {}".format(self.current_block))
                self.parent.transition(MNFetchNewBlockState, block_contender=self.current_block)
            else:
                self.log.warning("No more pending blocks. Transitioning back to RunState /w success=False")
                self.parent.transition(MNRunState, success=False)

    def _new_block_procedure(self, block, txs):
        self.log.debug("DONE COLLECTING BLOCK DATA FROM LEAVES. Storing new block.")

        hash_of_nodes = MerkleTree.hash_nodes(block.merkle_leaves)
        tree = b"".join(block.merkle_leaves).hex()
        signatures = "".join([merk_sig.signature for merk_sig in block.signatures])

        # Store the block + transaction data
        # TODO -- put this in its own class/module
        block_num = -1
        with DB() as db:
            tables = db.tables
            q = insert(tables.blocks).values(hash=hash_of_nodes, tree=tree, signatures=signatures)
            q_result = db.execute(q)
            block_num = q_result.lastrowid

            for key, value in txs.items():
                tx = {
                    'key': key,
                    'value': value
                }
                qq = insert(tables.transactions).values(tx)
                db.execute(qq)

        assert block_num > 0, "Block num must be greater than 0! Was it not set in the DB() context session?"

        # Notify delegates of new block
        self.log.info("Masternode sending NewBlockNotification to delegates with new block hash {} and block num {}"
                      .format(hash_of_nodes, block_num))
        notif = NewBlockNotification.create(new_block_hash=hash_of_nodes.hex(), new_block_num=block_num)
        self.parent.composer.send_pub_msg(filter=masternode_delegate, message=notif)

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

    def _prove_merkle(self, block):
        hash_of_nodes = MerkleTree.hash_nodes(block.merkle_leaves)
        tx_hashes = block.merkle_leaves[len(block.merkle_leaves) // 2:]

        if not MerkleTree.verify_tree(tx_hashes, hash_of_nodes):
            self.log.error("COULD NOT VERIFY MERKLE TREE FOR BLOCK CONTENDER {}".format(block))
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
        assert len(block.merkle_leaves) >= 1, "Masternode got block contender with no nodes! {}".format(block)
        assert len(block.signatures) >= majority, \
            "Received a block contender with only {} signatures (which is less than a majority of {}"\
            .format(len(block.signatures), majority)

        # TODO validate the sigs are actually from the top N delegates
        # TODO -- ensure that this block contender's previous block is this Masternode's current block...

        return self._validate_sigs(block) and self._prove_merkle(block)


@Masternode.register_state
class MNFetchNewBlockState(MNNewBlockState):

    # Enum to describe delegates we are requesting block data from. A delegate who has no pending requests is in
    # NODE_AVAILABLE state. Once a request is sent to a delegate we set it to NODE_AWAITING. If the request times out,
    # we set the timed out node to NODE_TIMEOUT
    NODE_AVAILABLE, NODE_AWAITING, NODE_TIMEOUT = range(3)

    def reset_attrs(self):
        super().reset_attrs()
        self.block_contender = None
        self.node_states = {}
        self.tx_hashes = []
        self.retrieved_txs = {}

    # Development sanity check (remove in production)
    @enter_from_any
    def enter_any(self, prev_state):
        raise Exception("MNFetchBlockState non-specific entry handler from state {} called! Uh oh!".format(prev_state))

    @enter_from(MNNewBlockState)
    def enter_from_new_block(self, prev_state, block_contender: BlockContender):
        self.reset_attrs()
        self.log.debug("Fetching block data for contender {}".format(block_contender))

        self.block_contender = block_contender
        self.tx_hashes = block_contender.merkle_leaves[len(block_contender.merkle_leaves) // 2:]

        # Populate self.node_states delegates who signed this block
        for sig in block_contender.signatures:
            self.node_states[sig.sender] = self.NODE_AVAILABLE

        repliers = list(self.node_states.keys())

        # Request individual block data from delegates
        for i in range(len(self.tx_hashes)):
            tx_hash = self.tx_hashes[i]
            vk = repliers[i % len(repliers)]
            self._request_from_delegate(tx_hash, vk)

    def _request_from_delegate(self, tx_hash: str, delegate_vk: str=''):
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

        self.log.debug("Requesting tx hash {} from VK {}".format(tx_hash, delegate_vk))

        req = TransactionRequest.create(tx_hash)
        self.parent.composer.send_request_msg(message=req, timeout=1, vk=delegate_vk)

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
    def recv_blockdata_reply(self, reply: TransactionReply):
        self.log.debug("Masternode got block data reply: {}".format(reply))

        if reply.tx_hash in self.tx_hashes:
            self.retrieved_txs[reply.tx_hash] = reply.raw_tx
        else:
            self.log.error("Received block data reply with tx hash {} that is not in tx_hashes")
            return

        if len(self.retrieved_txs) == len(self.tx_hashes):
            self.log.debug("Done collecting block data. Transitioning back to NewBlockState.")
            self.parent.transition(MNNewBlockState, success=True, retrieved_txs=self.retrieved_txs,
                                   pending_blocks=self.pending_blocks)
        else:
            self.log.debug("Still {} transactions yet to request until we can build the block"
                           .format(len(self.tx_hashes) - len(self.retrieved_txs)))

    @input_timeout(TransactionRequest)
    def timeout_block_req(self, request: TransactionRequest, envelope: Envelope):
        self.log.warning("TransactionRequest timed out for envelope with request data")
        self.log.debug("Envelope Data: {}".format(envelope))

        # TODO -- implement a way to get the VK of the dude we originally requested from
        # TODO also it appears timeouts are not working....need to fix integration tests on this and see whatsup
