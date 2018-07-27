from cilantro import Constants
from cilantro.protocol.structures import MerkleTree
from cilantro.protocol.wallets import ED25519Wallet
from cilantro.nodes.delegate.delegate import Delegate, DelegateBaseState
from cilantro.protocol.statemachine import *
from cilantro.messages import *
from cilantro.db import *


DelegateBootState = "DelegateBootState"
DelegateInterpretState = "DelegateInterpretState"
DelegateConsensusState = "DelegateConsensusState"
DelegateCatchupState = "DelegateCatchupState"


@Delegate.register_state
class DelegateConsensusState(DelegateBaseState):
    """
    Consensus state is where delegates pass around a merkelized version of their transaction queues, publish them to
    one another, confirm the signature is valid, and then vote/tally the results
    """
    NUM_DELEGATES = len(Constants.Testnet.Delegates)

    def reset_attrs(self):
        self.signatures = []
        self.signature = None
        self.merkle = None
        self.in_consensus = False

    @enter_from_any
    def enter_any(self, prev_state):
        # Development sanity check (TODO remove in production)
        raise Exception("ConsensusState should only be entered from interpret state! prev_state={}".format(prev_state))

    @enter_from(DelegateInterpretState)
    def enter_from_interpret(self):
        assert self.parent.interpreter.queue_size > 0, "Entered consensus state, but interpreter queue is empty!"

        # Merkle-ize transaction queue and create signed merkle hash
        all_tx = self.parent.interpreter.queue_binary
        self.log.info("Delegate got tx from interpreter queue: {}".format(all_tx))
        self.merkle = MerkleTree.from_raw_transactions(all_tx)
        self.log.info("Delegate got merkle hash {}".format(self.merkle.root_as_hex))
        self.signature = ED25519Wallet.sign(self.parent.signing_key, self.merkle.root)

        # Create merkle signature message and publish it
        merkle_sig = MerkleSignature.create(sig_hex=self.signature, timestamp='now',
                                            sender=self.parent.verifying_key)
        self.log.info("Broadcasting signature {}".format(self.signature))
        self.parent.composer.send_pub_msg(filter=Constants.ZmqFilters.DelegateDelegate, message=merkle_sig)

        # Now that we've computed/composed the merkle tree hash, validate all our pending signatures
        for sig in [s for s in self.parent.pending_sigs if self.validate_sig(s)]:
            self.signatures.append(sig)

        self.check_majority()

    @exit_to_any
    def exit_any(self, next_state):
        self.reset_attrs()

    def validate_sig(self, sig: MerkleSignature) -> bool:
        assert self.merkle is not None, "Cannot validate signature without our merkle set"
        self.log.debug("Validating signature: {}".format(sig))

        # Verify sender's vk exists in the state
        if sig.sender not in VKBook.get_delegates():
            self.log.debug("Received merkle sig from sender {} who was not registered nodes {}"
                           .format(sig.sender, VKBook.get_delegates()))
            return False
        # Verify we haven't received this signature already
        if sig in self.signatures:
            self.log.debug("Already received a signature from sender {}".format(sig.sender))
            return False

        # Below is just for debugging, so we can see if a signature cannot be verified
        if not sig.verify(self.merkle.root):
            self.log.warning("Delegate could not verify signature {}".format(sig))

        return sig.verify(self.merkle.root)

    def check_majority(self):
        self.log.debug("delegate has {} signatures out of {} total delegates"
                       .format(len(self.signatures), self.NUM_DELEGATES))

        if len(self.signatures) >= Constants.Testnet.Majority:
            self.log.info("Delegate in consensus!")
            self.in_consensus = True

            # DEBUG LINE TODO remove later
            self.log.critical("Delegate creating contender with merk leaves {}".format(self.merkle.leaves_as_hex))

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
        self.log.debug("delegate got tx request: {}".format(request))
        tx_blobs = []
        for tx_hash in request.tx_hashes:
            if tx_hash not in self.merkle.leaves_as_hex:
                self.log.error("Masternode requested tx hash {} that was not one of our merkle leaves!".format(tx_hash))
                continue
            tx_blobs.append(self.merkle.data_for_hash(tx_hash))

        reply = TransactionReply.create(raw_transactions=tx_blobs)
        self.log.debug("delegate replying to request with {}".format(reply))
        return reply

    @input(NewBlockNotification)
    def handle_new_block_notif(self, notif: NewBlockNotification):
        self.log.info("Delegate got new block notification: {}".format(notif))

        # DEBUG line -- TODO remove
        if not self.in_consensus:
            self.log.critical("Received a new block notification, but delegate not in consensus!")

        # If the new block hash is the same as our 'scratch block', then just copy scratch to state
        if notif.prev_block_hash == self.parent.current_hash and self.in_consensus:
            self.log.critical("Prev block hash matches ours. We in consensus!")

            self.parent.interpreter.flush(update_state=True)

            # DEBUG LINES TODO remove
            self.log.critical("delegate current block hash: {}".format(self.parent.current_hash))
            self.log.critical("database latest block hash: {}".format(BlockStorageDriver.get_latest_block_hash()))
            self.log.critical("about to store block with prev hash {} and current hash {}".format(notif.prev_block_hash, notif.block_hash))
            # END DEBUG

            BlockStorageDriver.store_block_from_meta(notif)
            self.parent.transition(DelegateInterpretState)

        # Otherwise, our block is out of consensus and we must request the latest from a Masternode!
        else:
            self.log.critical("New block has prev hash {} that does not match our current block hash {} ... :( :("
                             .format(notif.prev_block_hash, self.parent.current_hash))
            self.parent.transition(DelegateCatchupState)
