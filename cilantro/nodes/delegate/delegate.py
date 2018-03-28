"""
    Delegates

    Delegates are the "miners" of the Cilantro blockchain in that they opportunistically bundle up transaction into
    blocks and are rewarded with TAU for their actions. They receive approved transaction from delegates and broadcast
    blocks based on a 1 second or 10,000 transaction limit per block. They should be able to connect/drop from the
    network seamlessly as well as coordinate blocks amongst themselves.

     Delegate logic:
        Step 1) Delegate takes 10k transaction from witness and forms a block
        Step 2) Block propagates across the network to other delegates
        Step 3) Delegates pass around in memory DB hash to confirm they have the same blockchain state
        Step 4) Next block is mined and process repeats

        zmq pattern: subscribers (delegates) need to be able to communicate with one another. this can be achieved via
        a push/pull pattern where all delegates push their state to sink that pulls them in, but this is centralized.
        another option is to use ZMQ stream to have the tcp sockets talk to one another outside zmq
"""

from cilantro import Constants
from cilantro.logger import get_logger
from cilantro.nodes import NodeBase
from cilantro.protocol.statemachine import State, recv, timeout, recv_req
from cilantro.protocol.structures import MerkleTree
from cilantro.messages import StandardTransaction, TransactionBase, BlockContender, Envelope, MerkleSignature

from cilantro.protocol.interpreters import VanillaInterpreter
from cilantro.protocol.wallets import ED25519Wallet

from cilantro.db.delegate import LevelDBBackend, TransactionQueue
from cilantro.db.delegate.backend import PATH


class DelegateBaseState(State):
    def enter(self, prev_state): pass

    def exit(self, next_state): pass

    def run(self): pass

    @recv(TransactionBase)
    def recv_tx(self, tx: TransactionBase):
        self.log.debug("Delegate not interpreting transactions, adding {} to queue".format(tx))
        self.parent.pending_txs.append(tx)
        self.log.debug("{} transactions pending interpretation".format(self.parent.pending_txs))

    @recv(MerkleSignature)
    def recv_sig(self, sig: MerkleSignature):
        self.log.debug("Received signature with data {} but not in consensus, adding it to queue"
                       .format(sig._data))
        self.parent.pending_sigs.append(sig)


class DelegateBootState(DelegateBaseState):
    def enter(self, prev_state):
        # Sub to other delegates
        for delegate in [d for d in Constants.Testnet.Delegates if d['url'] != self.parent.url]:
            self.log.info("{} subscribing to delegate {}".format(self.parent.url, delegate['url']))
            self.parent.reactor.add_sub(url=delegate['url'])
        # Sub to witnesses
        for witness in Constants.Testnet.Witnesses:
            self.log.info("{} subscribing to witness {}".format(self.parent.url, witness['url']))
            self.parent.reactor.add_sub(url=witness['url'])
        # Pub on our own url
        self.parent.reactor.add_pub(url=self.parent.url)

    def run(self):
        self.parent.transition(DelegateInterpretState)

    def exit(self, next_state):
        self.parent.reactor.notify_ready()


class DelegateInterpretState(DelegateBaseState):
    def __init__(self, state_machine=None):
        super().__init__(state_machine=state_machine)
        self.interpreter = VanillaInterpreter(backend=self.parent.backend)

    def enter(self, prev_state):
        self.log.debug("Flushing pending tx queue of {} txs".format(len(self.parent.pending_txs)))
        for tx in self.parent.pending_txs:
            self.interpret_tx(tx)
        self.parent.pending_txs = []

    def exit(self, next_state):
        # Flush queue if we are not leaving interpreting for consensus
        if next_state is not DelegateConsensusState:
            self.parent.queue.flush()  # TODO -- put proper api call here

    @recv(TransactionBase)
    def recv_tx(self, tx: TransactionBase):
        self.interpret_tx(tx=tx)

    def interpret_tx(self, tx: TransactionBase):
        try:
            self.log.debug("Interpreting standard tx")
            self.interpreter.interpret_transaction(tx)
        except Exception as e:
            self.log.error("Error interpreting tx: {}".format(e))

        self.log.debug("Successfully interpreted tx...adding it to queue")
        self.parent.queue.push(tx.serialize())

        if self.parent.queue.size >= Constants.Nodes.MaxQueueSize:
            self.log.info("Consensus time!")
            self.parent.transition(DelegateConsensusState)
        else:
            self.log.debug("Not consensus time yet, queue is only size {}/{}"
                           .format(self.parent.queue.size, Constants.Nodes.MaxQueueSize))


class DelegateConsensusState(DelegateBaseState):
    NUM_DELEGATES = len(Constants.Testnet.Delegates)

    def __init__(self, state_machine=None):
        super().__init__(state_machine=state_machine)
        self.signatures = []
        self.signature = None
        self.merkle = None
        self.merkle_hash = None

    def enter(self, prev_state):
        assert self.parent.queue.size >= Constants.Nodes.MaxQueueSize, "In consensus state, but queue not full"

        # Merkle-ize transaction queue and create signed merkle hash
        all_tx = self.parent.queue.flush()
        self.merkle = MerkleTree(all_tx)
        self.merkle_hash = self.merkle.hash_of_nodes()
        self.signature = ED25519Wallet.sign(self.parent.signing_key, self.merkle_hash)

        # Create merkle signature message and publish it
        merkle_sig = MerkleSignature.from_fields(sig_hex=self.signature, timestamp='now', sender=self.parent.url)
        sig_msg = Envelope.create(merkle_sig)
        self.log.info("Broadcasting signature")
        self.parent.reactor.pub(url=self.parent.url, data=sig_msg.serialize())

        # Now that we've computed the merkle tree hash, validate all our pending signatures
        for sig in [s for s in self.parent.pending_sigs if self.validate_sig(s)]:
            self.signatures.append(sig)

    def run(self):
        self.check_majority()

    def exit(self, next_state):
        self.signatures, self.signature, self.merkle, self.merkle_hash = [], None, None, None

    def validate_sig(self, sig: MerkleSignature) -> bool:
        assert self.merkle_hash is not None, "Cannot validate signature without our merkle hash set"
        self.log.debug("Validating signature: {}".format(sig))

        # Sanity checks
        if sig.sender not in self.parent.nodes_registry:
            self.log.critical("Received merkle sig from sender {} who was not registered nodes {}"
                              .format(sig.sender, self.parent.nodes_registry))
            return False
        if sig in self.signatures:
            self.log.critical("Already received a signature from sender {}".format(sig.sender))
            return False
        if not sig.verify(self.merkle_hash, self.parent.nodes_registry[sig.sender]):  # this check is just for debugging
            self.log.critical("Delegate could not verify signature: {}".format(sig))

        return sig.verify(self.merkle_hash, self.parent.nodes_registry[sig.sender])

    def check_majority(self):
        self.log.debug("delegate has {} signatures out of {} total delegates"
                       .format(len(self.signatures), self.NUM_DELEGATES))

        if len(self.signatures) > self.NUM_DELEGATES // 2:
            self.log.critical("\n\n\nDelegate in consensus!\n\n\n")
            # TODO -- successful consensus logic
            # once update confirmed from mn, transition to update state

    @receive(MerkleSignature)
    def recv_sig(self, sig: MerkleSignature):
        if self.validate_sig(sig):
            self.signatures.append(sig)
            self.check_majority()


class DelegateUpdateState(DelegateBaseState): pass


class Delegate(NodeBase):
    _INIT_STATE = DelegateBootState
    _STATES = [DelegateBootState, DelegateInterpretState, DelegateConsensusState, DelegateUpdateState]

    def __init__(self, url=None, signing_key=None, slot=0):
        if url is None and signing_key is None:
            node_info = Constants.Testnet.Delegates[slot]
            url = node_info['url']
            signing_key = node_info['sk']

        # Shared between states
        self.pending_sigs, self.pending_txs = [], []  # TODO -- use real queue objects here
        db_path = PATH + '_' + str(slot)
        self.backend = LevelDBBackend(path=db_path)
        self.queue = TransactionQueue(backend=self.backend)

        super().__init__(url=url, signing_key=signing_key)

        self.log = get_logger("Delegate-#{}".format(slot), auto_bg_val=slot)
        self.log.info("Delegate being created on slot {} with url {}, and backend path {}"
                      .format(url, signing_key, db_path))
