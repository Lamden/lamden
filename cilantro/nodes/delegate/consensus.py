from cilantro.protocol.structures import MerkleTree
from cilantro.protocol.wallet import Wallet
from cilantro.nodes.delegate.delegate import Delegate, DelegateBaseState
from cilantro.protocol.statemachine import *
from cilantro.messages import *
from cilantro.db import *
from cilantro.constants.zmq_filters import delegate_delegate
from cilantro.constants.testnet import majority, delegates

DelegateBootState = "DelegateBootState"
DelegateInterpretState = "DelegateInterpretState"
DelegateConsensusState = "DelegateConsensusState"


@Delegate.register_state
class DelegateConsensusState(DelegateBaseState):
    """Consensus state is where delegates pass around a merkelized version of their transaction queues, publish them to
    one another, confirm the signature is valid, and then vote/tally the results"""
    NUM_DELEGATES = len(delegates)

    """
    TODO -- move this 'variable setting' logic outside of init. States should have their own constructor, which init
    will call in the superclass. Optionally, states should be able to set a variable if they want all their properties
    flushed each time.
    """

    def reset_attrs(self):
        self.signatures = []
        self.signature = None
        self.merkle = None
        self.merkle_hash = None
        self.in_consensus = False

    # TODO -- i think this should only occur when entering from Interpretting state yea?
    @enter_from_any
    def enter_any(self, prev_state):
        assert self.parent.interpreter.queue_size > 0, "Entered consensus state, but interpreter queue is empty!"

        # Merkle-ize transaction queue and create signed merkle hash
        all_tx = self.parent.interpreter.queue_binary
        self.log.info("Delegate got tx from interpreter queue: {}".format(all_tx))
        self.merkle = MerkleTree(all_tx)
        self.merkle_hash = self.merkle.hash_of_nodes()
        self.log.info("Delegate got merkle hash {}".format(self.merkle_hash))
        self.signature = Wallet.sign(self.parent.signing_key, self.merkle_hash)

        # Create merkle signature message and publish it
        merkle_sig = MerkleSignature.create(sig_hex=self.signature, timestamp='now',
                                            sender=self.parent.verifying_key)
        self.log.info("Broadcasting signature {}".format(self.signature))
        self.parent.composer.send_pub_msg(filter=delegate_delegate, message=merkle_sig)

        # Now that we've computed/composed the merkle tree hash, validate all our pending signatures
        for sig in [s for s in self.parent.pending_sigs if self.validate_sig(s)]:
            self.signatures.append(sig)

        self.check_majority()

    @exit_to_any
    def exit_any(self, next_state):
        self.reset_attrs()

    def validate_sig(self, sig: MerkleSignature) -> bool:
        assert self.merkle_hash is not None, "Cannot validate signature without our merkle hash set"
        self.log.debug("Validating signature: {}".format(sig))

        # Verify sender's vk exists in the state
        if sig.sender not in VKBook.get_delegates():
            self.log.debug("Received merkle sig from sender {} who was not registered nodes {}"
                              .format(sig.sender, VKBook.get_delegates()))
            return False
        # Verify we havne't received this signature already
        if sig in self.signatures:
            self.log.debug("Already received a signature from sender {}".format(sig.sender))
            return False

        # Below is just for debugging, so we can see if a signature cannot be verified
        if not sig.verify(self.merkle_hash):
            self.log.warning("Delegate could not verify signature")
            self.log.debug("Signature: {}".format(sig))

        return sig.verify(self.merkle_hash)

    def check_majority(self):
        self.log.debug("delegate has {} signatures out of {} total delegates"
                       .format(len(self.signatures), self.NUM_DELEGATES))

        if len(self.signatures) >= majority:
            self.log.info("Delegate in consensus!")
            self.in_consensus = True

            # Create BlockContender and send it to all Masternode(s)
            bc = BlockContender.create(signatures=self.signatures, merkle_leaves=self.merkle.nodes)
            for mn_vk in VKBook.get_masternodes():
                self.parent.composer.send_request_msg(message=bc, vk=mn_vk)

    @input(MerkleSignature)
    def handle_sig(self, sig: MerkleSignature):
        if self.validate_sig(sig):
            self.signatures.append(sig)
            self.check_majority()

    @input_request(BlockDataRequest)
    def handle_blockdata_req(self, block_data: BlockDataRequest):
        # Development check -- should be removed in production
        assert block_data.tx_hash in self.merkle.leaves, "Block hash {} not found in leaves {}"\
            .format(block_data.tx_hash, self.merkle.leaves)

        # import time
        # self.log.debug("sleeping...")
        # time.sleep(1.2)
        # self.log.debug("done sleeping")

        tx_binary = self.merkle.data_for_hash(block_data.tx_hash)
        self.log.info("Replying to tx hash request {} with tx binary: {}".format(block_data.tx_hash, tx_binary))
        reply = BlockDataReply.create(tx_binary)
        return reply

    @input(NewBlockNotification)
    def handle_new_block_notif(self, notif: NewBlockNotification):
        self.log.info("Delegate got new block notification: {}".format(notif))

        # If the new block hash is the same as our 'scratch block', then just copy scratch to state
        if bytes.fromhex(notif.block_hash) == self.merkle_hash:
            self.log.debug("New block hash is the same as ours!!!")
            self.update_from_scratch(new_block_hash=notif.block_hash, new_block_num=notif.block_num)
            self.parent.transition(DelegateInterpretState)
        # Otherwise, our block is out of consensus and we must request the latest from a Masternode
        else:
            self.log.warning("New block hash {} does not match out own merkle_hash {}"
                              .format(notif.block_hash, self.merkle_hash))
            # self.parent.transition(DelegateOutConsensusUpdateState)

    def update_from_scratch(self, new_block_hash, new_block_num):
        self.log.info("Copying Scratch to State")
        self.parent.interpreter.flush(update_state=True)

        self.log.info("Updating state_meta with new hash {} and block num {}".format(new_block_hash, new_block_num))
        with DB() as db:
            db.execute('delete from state_meta')
            q = insert(db.tables.state_meta).values(number=new_block_num, hash=new_block_hash)
            db.execute(q)
