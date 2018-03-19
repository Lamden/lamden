from cilantro.protocol.wallets import ED25519Wallet
from cilantro.logger.base import get_logger
from cilantro import Constants
from cilantro.messages import StandardTransaction, Envelope
from cilantro.messages.consensus import MerkleSignature
from cilantro.protocol.structures import MerkleTree
from cilantro.messages.envelope import MODEL_TYPES # TODO -- find a better home for these constants
from cilantro.db.delegate.transaction_queue_driver import TransactionQueueDriver
from cilantro.protocol.interpreters import VanillaInterpreter

from cilantro.protocol.reactor import NetworkReactor
# if sys.platform != 'win32':
#     import uvloop
#     asyncio.set_event_loop_policy(uvloop.EventLoopPolicy)

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
from cilantro.nodes import NodeBase
from cilantro.protocol.statemachine import State, receive
from cilantro.protocol.structures import MerkleTree
from cilantro.messages import StandardTransaction, BlockContender, Envelope, MerkleSignature
# TODO -- test receive decorator with inheritance.. shud work cuz the child recv will overwrite the parent recv key in registry

class DelegateBaseState(State):
    def enter(self, prev_state): pass
    def exit(self, next_state): pass
    def run(self): pass

    @receive(StandardTransaction)
    def recv_tx(self, tx: StandardTransaction):
        self.log.debug("Delegate not interpreting transactions, adding {} to queue".format(tx))
        self.parent.pending_txs.append(tx)
        self.log.debug("{} transactions pending interpretation".format(self.parent.pending_txs))

    @receive(MerkleSignature)
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
        self.interpreter = VanillaInterpreter()

    def enter(self, prev_state):
        self.log.debug("Flushing pending tx queue of {} txs".format(len(self.parent.pending_txs)))
        for tx in self.parent.pending_txs:
            self.interpret_tx(tx)
        self.parent.pending_txs = []

    def exit(self, next_state):
        # Flush queue if we are not leaving interpreting for consensus
        if next_state is not DelegateConsensusState:
            self.parent.queue.dequeue_all()  # TODO -- put proper api call here

    @receive(StandardTransaction)
    def recv_tx(self, tx: StandardTransaction):
        self.interpret_tx(tx=tx)

    def interpret_tx(self, tx: StandardTransaction):
        try:
            self.log.debug("Interpreting standard tx")
            self.interpreter.interpret_transaction(tx)
        except Exception as e:
            self.log.error("Error interpreting tx: {}".format(e))

        self.log.debug("Successfully interpreted tx...adding it to queue")
        self.parent.queue.enqueue_transaction(tx.serialize())

        if self.parent.queue.queue_size() >= Constants.Nodes.MaxQueueSize:
            self.log.info("Consensus time!")
            self.parent.transition(DelegateConsensusState)
        else:
            self.log.debug("Not consensus time yet, queue is only size {}/{}"
                           .format(self.parent.queue.queue_size(), Constants.Nodes.MaxQueueSize))


class DelegateConsensusState(DelegateBaseState):
    NUM_DELEGATES = len(Constants.Testnet.Delegates)

    def __init__(self, state_machine=None):
        super().__init__(state_machine=state_machine)
        self.signatures = []
        self.signature = None
        self.merkle = None
        self.merkle_hash = None
        # self.signatures, self.signature, self.merkle, self.merkle_hash, self.sent_update = [], None, None, None, False

    def enter(self, prev_state):
        assert self.parent.queue.queue_size() >= Constants.Nodes.MaxQueueSize, "In consensus state, but queue not full"

        # Merkle-ize transaction queue and create signed merkle hash
        all_tx = self.parent.queue.dequeue_all()
        self.merkle = MerkleTree(all_tx)
        self.merkle_hash = self.merkle.hash_of_nodes()
        self.signature = ED25519Wallet.sign(self.parent.signing_key, self.merkle_hash)

        # Create merkle signature message and publish it
        merkle_sig = MerkleSignature.from_fields(sig_hex=self.signature, timestamp='now', sender=self.parent.url)
        sig_msg = Envelope.create(merkle_sig)
        self.log.info("Broadcasting signature")
        self.parent.reactor.pub(url=self.parent.url, data=sig_msg.serialize())

        # Now that we have the merkle hash, validate all our pending signatures
        for sig in [s for s in self.parent.pending_sigs if self.validate_sig(s)]:
            self.signatures.append(sig)

    def run(self):
        self.check_majority()

    def exit(self, next_state):
        self.signatures, self.signature, self.merkle, self.merkle_hash = [], None, None, None

    def validate_sig(self, sig: MerkleSignature) -> bool:
        self.log.debug("Validating signature: {}".format(sig))

        # Sanity checks
        if sig.sender not in self.parent.nodes_registry:
            self.log.critical("Received merkle sig from sender {} who was not registered nodes {}")
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
        # this is what we had before: if len(self.signatures) > (len(self.delegates) + 1) // 2:
        # they are equivalent right?
        if len(self.signatures) > self.NUM_DELEGATES // 2:
            self.log.critical("Delegate in consensus!")
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
            self.log.info("Delegate being created on slot {} with url {}".format(url, signing_key))
        super().__init__(url=url, signing_key=signing_key)

        # Shared between states
        self.pending_sigs, self.pending_txs = [], []  # TODO -- use real queue objects here
        self.queue = TransactionQueueDriver(db=self.url[-1]) # TODO -- replace this with new RocksDB


# class Delegate:
#     def __init__(self, url, delegates: dict, signing_key):
#         self.port = int(url[-4:])
#         self.log = get_logger("Delegate-{}".format(self.port), auto_bg_val=self.port)
#         self.url = url
#
#         self.log.info("Spinning up delegate /w url={}".format(self.url))
#
#         self.delegates = delegates
#         # Remove self from delegates hash
#         del self.delegates[url]
#         self.log.debug("delegates (excluding self): {}".format(self.delegates))
#         self.signing_key = signing_key
#
#         # consensus variables
#         self.merkle = None
#         self.signature = b'too soon bro'
#         self.signatures, self.failed_signatures = {}, {}
#
#         # Setup reactor, subscribe to witness
#         self.reactor = NetworkReactor(self)
#         witness_url = 'tcp://127.0.0.1:{}'.format(Constants.Witness.PubPort)
#         self.reactor.add_sub(url=witness_url, callback='handle_message')
#
#         # Sub to other delegates
#         for d_url in self.delegates:
#             self.reactor.add_sub(url=d_url, callback='handle_message')
#
#         # Publish on our own URL
#         self.reactor.add_pub(url=self.url)
#
#         # Queue + Interpreter
#         self.queue = TransactionQueueDriver(db=str(self.port)[-1:])
#         self.interpreter = VanillaInterpreter(port=str(self.port))
#
#         # Flush queue on boot
#         self.log.debug("Delegate flushing queue on boot")
#         self.queue.dequeue_all()
#
#         # Notify reactor that this node is ready to flex
#         self.reactor.notify_ready()
#
#     def handle_message(self, msg):
#         # self.log.debug("Got message: {}".format(msg))
#         m = None
#         try:
#             m = Envelope.from_bytes(msg)
#         except Exception as e:
#             self.log.error("Error deserializing msg: {}".format(e))
#
#         # Route m
#         if m.type == MODEL_TYPES[StandardTransaction.name]['id']:
#             self.handle_tx(m.payload)
#         elif m.type == MODEL_TYPES[MerkleSignature.name]['id']:
#             self.handle_sig(m.payload)
#         else:
#             self.log.error("Got message of unknown type: {}".format(m.type))
#             raise ValueError("Got message of unknown type: {}".format(m.type))
#
#     def handle_tx(self, tx_binary):
#         self.log.debug("Unpacking standard tx")
#         tx = None
#
#         # Deserialize tx
#         try:
#             tx = StandardTransaction.from_bytes(tx_binary)
#         except Exception as e:
#             self.log.error("Error unpacking standard transaction: {}".format(e))
#
#         # Feed tx to interpreter
#         try:
#             self.log.debug("Interpreting standard tx")
#             self.interpreter.interpret_transaction(tx)
#         except Exception as e:
#             self.log.error("Error interpreting tx: {}".format(e))
#
#         self.log.debug("Successfully interpreted tx...adding it to queue")
#         self.queue.enqueue_transaction(tx.serialize())
#
#         if self.queue.queue_size() >= 4:
#             self.gather_consensus()
#
#     def handle_sig(self, sig_payload):
#         sig = MerkleSignature.from_bytes(sig_payload)
#         self.log.debug("Received signature with data {}".format(sig._data))
#
#         # Sanity check (for debugging purposes)
#         if (sig.sender in self.signatures) or (sig.sender in self.failed_signatures):
#             self.log.error("OH NO -- this delegate already has a signature from {}".format(sig.sender))
#             return
#
#         if sig.verify(self.merkle.hash_of_nodes(), self.delegates[sig.sender]):
#             self.log.debug("Signature validated from sender {}".format(sig.sender))
#             self.signatures[sig.sender] = sig
#         else:
#             self.log.warning("!!! Signature NOT validated from sender {}".format(sig.sender))
#             self.failed_signatures[sig.sender] = sig
#
#         self.log.debug("Number of sigs: {}".format(len(self.signatures)))
#
#         if len(self.signatures) > (len(self.delegates) + 1) // 2:
#             self.log.critical("Were in consensus!!! sigs={}".format(self.signatures))
#             # TODO -- successful consensus logic
#
#     def gather_consensus(self):
#         self.log.debug("Starting consesnsus with peers: {}".format(self.delegates))
#
#         # Merkle-ize tx and sign
#         tx = self.queue.dequeue_all()
#         self.merkle = MerkleTree(tx)
#         self.signature = ED25519Wallet.sign(self.signing_key, self.merkle.hash_of_nodes())
#         self.log.critical('Signature for merkle is {}'.format(self.signature))
#
#         # Create merkle signature message
#         merkle_sig = MerkleSignature.from_fields(sig_hex=self.signature, timestamp='now', sender=self.url)
#         sig_msg = Envelope.create(MerkleSignature, merkle_sig.serialize())
#
#         self.log.info("Broadcasting signatures...")
#         self.reactor.pub(url=self.url, data=sig_msg.serialize())
#         self.log.info("Done broadcasting signatures.")



