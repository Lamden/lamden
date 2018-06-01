from cilantro import Constants
from cilantro.protocol.statemachine import *
from cilantro.nodes.masternode import MNBaseState, Masternode
from cilantro.db import *
from cilantro.messages import *
from cilantro.protocol.structures import MerkleTree
from collections import deque


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

            # TODO store new block
            self.new_block_procedure(block=self.current_block, txs=retrieved_txs)

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

    def new_block_procedure(self, block, txs):
        self.log.critical("\n***\nDONE COLLECTING BLOCK DATA FROM NODES. Storing new block.\n***\n")

        hash_of_nodes = MerkleTree.hash_nodes(block.nodes)
        tree = b"".join(block.nodes).hex()
        signatures = "".join([merk_sig.signature for merk_sig in block.signatures])

        # Store the block + transaction data
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
        self.parent.composer.send_pub_msg(filter=Constants.ZmqFilters.MasternodeDelegate, message=notif)

    @input(BlockContender)
    def handle_block_contender(self, block: BlockContender):
        if self.validate_block_contender(block):
            self.pending_blocks.append(block)

    def validate_block_contender(self, block: BlockContender) -> bool:
        """
        Helper method to validate a block contender. For a block contender to be valid it must:
        1) Have a provable merkle tree, ie. all nodes must be hash of (left child + right child)
        2) Be signed by at least 2/3 of the top 32 delegates
        :param block_contender: The BlockContender to validate
        :return: True if the BlockContender is valid, false otherwise
        """
        def _validate_sigs(signatures, msg) -> bool:
            for sig in signatures:
                self.log.info("mn verifying signature: {}".format(sig))
                if not sig.verify(msg, sig.sender):
                    self.log.error("!!!! Oh no why couldnt we verify sig {}???".format(sig))
                    return False
            return True

        # Development sanity checks (these should be removed in production)
        assert len(block.nodes) >= 1, "Masternode got block contender with no nodes! {}".format(block)
        assert len(block.signatures) >= Constants.Testnet.Majority, \
            "Received a block contender with only {} signatures (which is less than a majority of {}"\
            .format(len(block.signatures), Constants.Testnet.Majority)

        # TODO -- ensure that this block contender's previous block is this Masternode's current block...

        # Prove Merkle Tree
        hash_of_nodes = MerkleTree.hash_nodes(block.nodes)
        tx_hashes = block.nodes[len(block.nodes) // 2:]
        if not MerkleTree.verify_tree(tx_hashes, hash_of_nodes):
            self.log.error("\n\n\n\nCOULD NOT VERIFY MERKLE TREE FOR BLOCK CONTENDER {}\n\n\n".format(block))
            return False

        # Validate signatures
        if not _validate_sigs(block.signatures, hash_of_nodes):
            self.log.error("MN COULD NOT VALIDATE SIGNATURES FOR CONTENDER {}".format(block))
            return False

        return True


@Masternode.register_state
class MNFetchNewBlockState(MNNewBlockState):
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
        self.tx_hashes = block_contender.nodes[len(block_contender.nodes) // 2:]

        # Add dealer sockets for Delegates to fetch block tx data
        for sig in block_contender.signatures:
            vk = sig.sender
            self.node_states[sig.sender] = self.NODE_AVAILABLE
            self.parent.composer.add_dealer(vk=vk)

            # TODO experiment if this still works without sleeps (i think it should)
            import time
            time.sleep(0.1)

        repliers = list(self.node_states.keys())

        # Request individual block data from delegates
        for i in range(len(self.tx_hashes)):
            tx = self.tx_hashes[i]
            replier_vk = repliers[i % len(repliers)]
            req = BlockDataRequest.create(tx)

            self.log.debug("Requesting tx hash {} from VK {}".format(tx, replier_vk))
            self.parent.composer.send_request_msg(message=req, timeout=1, vk=replier_vk)

    @input(BlockDataReply)
    def recv_blockdata_reply(self, reply: BlockDataReply):
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

    @input_timeout(BlockDataRequest)
    def timeout_block_req(self, request: BlockDataRequest, envelope: Envelope):
        self.log.info("\n\nBlockDataRequest timed out for envelope with request data {}\n\n".format(envelope, request))
        # TODO -- implement
