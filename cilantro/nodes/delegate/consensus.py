from cilantro.protocol.structures import MerkleTree
from cilantro.protocol import wallet
from cilantro.nodes.delegate.delegate import Delegate, DelegateBaseState

from cilantro.protocol.states.decorators import input, enter_from_any, enter_from, exit_to_any, input_request, timeout_after

from cilantro.messages.consensus.merkle_signature import MerkleSignature
from cilantro.messages.consensus.block_contender import BlockContender
from cilantro.messages.block_data.block_metadata import NewBlockNotification
from cilantro.messages.block_data.transaction_data import TransactionReply, TransactionRequest

from cilantro.constants.zmq_filters import DELEGATE_DELEGATE_FILTER
from cilantro.constants.testnet import MAJORITY, TESTNET_DELEGATES
from cilantro.constants.nodes import BLOCK_SIZE
from cilantro.constants.delegate import CONSENSUS_TIMEOUT

from cilantro.storage.db import VKBook
from cilantro.storage.blocks import BlockStorageDriver

DelegateBootState = "DelegateBootState"
DelegateInterpretState = "DelegateInterpretState"
DelegateConsensusState = "DelegateConsensusState"
DelegateCatchupState = "DelegateCatchupState"


@Delegate.register_state
class DelegateConsensusState(DelegateBaseState):
    """
    Consensus state is where TESTNET_DELEGATES pass around a merkelized version of their transaction queues, publish them to
    one another, confirm the signature is valid, and then vote/tally the results
    """

    NUM_DELEGATES = len(TESTNET_DELEGATES)

    def reset_attrs(self):
        self.signatures = []
        self.signature = None
        self.merkle = None
        self.in_consensus = False

    @timeout_after(CONSENSUS_TIMEOUT)
    def timeout(self):
        self.log.fatal("Consensus state exceeded timeout duration of {} seconds! Transitioning to CatchUpState".format(CONSENSUS_TIMEOUT))
        self.parent.interpreter.flush(update_state=False)
        self.parent.transition(DelegateCatchupState)

    @enter_from_any
    def enter_any(self, prev_state):
        # Development sanity check (TODO remove in production)
        raise Exception("ConsensusState should only be entered from interpret state! prev_state={}".format(prev_state))

    @enter_from(DelegateInterpretState)
    def enter_from_interpret(self):
        assert self.parent.interpreter.queue_size > 0, "Entered consensus state, but interpreter queue is empty!"
        assert self.parent.interpreter.queue_size == BLOCK_SIZE, \
            "Consensus state entered with {} transactions in queue, but the BLOCK_SIZE is {}!"\
            .format(self.parent.interpreter.queue_size, BLOCK_SIZE)

        # Merkle-ize transaction queue and create signed merkle hash
        all_tx = self.parent.interpreter.queue_binary
        # self.log.debugv("Delegate got tx from interpreter queue: {}".format(all_tx))
        self.merkle = MerkleTree.from_raw_transactions(all_tx)
        self.log.debugv("Delegate got merkle hash {}".format(self.merkle.root_as_hex))
        self.signature = wallet.sign(self.parent.signing_key, self.merkle.root)

        # Create merkle signature message and publish it
        merkle_sig = MerkleSignature.create(sig_hex=self.signature, timestamp='now',
                                            sender=self.parent.verifying_key)
        self.log.debug("Broadcasting signature {}".format(self.signature))
        self.parent.composer.send_pub_msg(filter=DELEGATE_DELEGATE_FILTER, message=merkle_sig)

        # Now that we've computed/composed the merkle tree hash, validate all our pending signatures
        for sig in [s for s in self.parent.pending_sigs if self.validate_sig(s)]:
            self.signatures.append(sig)

        # Add our own signature
        self.signatures.append(merkle_sig)

        self.check_majority()

    @exit_to_any
    def exit_any(self):
        self.reset_attrs()

    def validate_sig(self, sig: MerkleSignature) -> bool:
        assert self.merkle is not None, "Cannot validate signature without our merkle set"
        self.log.debugv("Validating signature: {}".format(sig))

        # Verify sender's vk exists in the state
        if sig.sender not in VKBook.get_delegates():
            self.log.warning("Received merkle sig from sender {} who was not registered nodes {}"
                             .format(sig.sender, VKBook.get_delegates()))
            return False

        # Verify we haven't received this signature already
        if sig in self.signatures:
            self.log.warning("Already received a signature from sender {}".format(sig.sender))
            return False

        # Below is just for debugging, so we can see if a signature cannot be verified
        if not sig.verify(self.merkle.root):
            self.log.warning("Delegate could not verify signature! Different Merkle trees.\nSig: {}".format(sig))

        return sig.verify(self.merkle.root)

    def check_majority(self):
        self.log.debug("delegate has {} signatures out of {} total TESTNET_DELEGATES"
                       .format(len(self.signatures), self.NUM_DELEGATES))

        if len(self.signatures) >= MAJORITY and not self.in_consensus:
            self.log.important("Delegate in consensus!")
            self.in_consensus = True

            # Create BlockContender and send it to all Masternode(s)
            bc = BlockContender.create(signatures=self.signatures, merkle_leaves=self.merkle.leaves_as_hex)
            for mn_vk in VKBook.get_masternodes():
                self.parent.composer.send_request_msg(message=bc, vk=mn_vk)

    @input(MerkleSignature)
    def handle_sig(self, sig: MerkleSignature):
        if self.validate_sig(sig):
            self.signatures.append(sig)
            self.check_majority()

    @input_request(TransactionRequest)
    def handle_tx_request(self, request: TransactionRequest):
        self.log.debugv("delegate got tx request: {}".format(request))

        tx_blobs = []
        for tx_hash in request.tx_hashes:
            if tx_hash not in self.merkle.leaves_as_hex:
                self.log.error("Masternode requested tx hash {} that was not one of our merkle leaves!".format(tx_hash))
                continue
            tx_blobs.append(self.merkle.data_for_hash(tx_hash))

        reply = TransactionReply.create(raw_transactions=tx_blobs)
        self.log.debugv("delegate replying to request with {}".format(reply))
        return reply

    @input(NewBlockNotification)
    def handle_new_block_notif(self, notif: NewBlockNotification):
        self.log.info("Delegate got new block notification: {}".format(notif))

        # If we were in consensus and the new block's prev hash matches out current, then commit all interpreted txs
        if notif.prev_block_hash == self.parent.current_hash and self.in_consensus:
            self.log.success("Prev block hash matches ours. Delegate in consensus!")

            BlockStorageDriver.store_block_from_meta(notif)
            self.parent.interpreter.flush(update_state=True)
            self.parent.transition(DelegateInterpretState)
            return

        # Otherwise, our block is out of consensus and we must request the latest from a Masternode
        else:
            # NOTE: the 2 'if' statements below are purely for debugging
            if self.in_consensus:  # TODO should this be an assertion?
                self.log.fatal("Delegate in consensus according to local state, but received new block notification "
                               "that does not match our previous block hash! ")
            if notif.prev_block_hash != self.parent.current_hash:
                self.log.critical("New block has prev hash {} that does not match our current block hash {}"
                                  .format(notif.prev_block_hash, self.parent.current_hash))

            self.log.notice("Delegate transitioning to CatchUpState")
            self.parent.transition(DelegateCatchupState)
            return
