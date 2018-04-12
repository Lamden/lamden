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
from cilantro.protocol.interpreters import VanillaInterpreter
from cilantro.protocol.wallets import ED25519Wallet
from cilantro.utils import TestNetURLHelper
from cilantro.messages import TransactionBase, BlockContender, Envelope, MerkleSignature, \
    BlockDataRequest, BlockDataReply


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
            self.parent.reactor.add_sub(url=TestNetURLHelper.pubsub_url(delegate['url']))
        # Sub to witnesses
        for witness in Constants.Testnet.Witnesses:
            self.log.info("{} subscribing to witness {}".format(self.parent.url, witness['url']))
            self.parent.reactor.add_sub(url=TestNetURLHelper.pubsub_url(witness['url']))

        # Pub on our own url
        self.parent.reactor.add_pub(url=TestNetURLHelper.pubsub_url(self.parent.url))

        # Add router socket
        self.parent.reactor.add_router(url=TestNetURLHelper.dealroute_url(self.parent.url))

        # Add dealer socket for Masternode
        self.parent.reactor.add_dealer(url=TestNetURLHelper.dealroute_url(Constants.Testnet.Masternode.InternalUrl),
                                       id=self.parent.url)

    def run(self):
        self.parent.transition(DelegateInterpretState)

    def exit(self, next_state):
        self.parent.reactor.notify_ready()


class DelegateInterpretState(DelegateBaseState):
    def __init__(self, state_machine=None):
        super().__init__(state_machine=state_machine)

    def enter(self, prev_state):
        self.log.debug("Flushing pending tx queue of {} txs".format(len(self.parent.pending_txs)))
        for tx in self.parent.pending_txs:
            self.interpret_tx(tx)
        self.parent.pending_txs = []

    def exit(self, next_state):
        # Flush queue if we are not leaving interpreting for consensus
        if type(next_state) is not DelegateConsensusState:
            self.log.critical("Delegate exiting interpreting for state {}, flushing queue".format(next_state))
            self.parent.interpreter.flush(update_state=False)

    @recv(TransactionBase)
    def recv_tx(self, tx: TransactionBase):
        self.interpret_tx(tx=tx)

    def interpret_tx(self, tx: TransactionBase):
        self.parent.interpreter.interpret_transaction(tx)

        self.log.debug("Size of queue: {}".format(len(self.parent.interpreter.queue)))

        if len(self.parent.interpreter.queue) >= Constants.Nodes.MaxQueueSize:
            self.log.info("Consensus time!")
            self.parent.transition(DelegateConsensusState)
        else:
            self.log.debug("Not consensus time yet, queue is only size {}/{}"
                           .format(len(self.parent.interpreter.queue), Constants.Nodes.MaxQueueSize))


class DelegateConsensusState(DelegateBaseState):
    NUM_DELEGATES = len(Constants.Testnet.Delegates)

    def __init__(self, state_machine=None):
        super().__init__(state_machine=state_machine)
        self.signatures = []
        self.signature = None
        self.merkle = None
        self.merkle_hash = None

    def enter(self, prev_state):
        # Merkle-ize transaction queue and create signed merkle hash
        all_tx = self.parent.interpreter.get_queue_binary()
        self.log.info("Delegate got tx from interpreter queue: {}".format(all_tx))
        self.merkle = MerkleTree(all_tx)
        self.merkle_hash = self.merkle.hash_of_nodes()
        self.signature = ED25519Wallet.sign(self.parent.signing_key, self.merkle_hash)

        # Create merkle signature message and publish it
        merkle_sig = MerkleSignature.create(sig_hex=self.signature, timestamp='now', sender=self.parent.url)
        self.log.info("Broadcasting signature {}".format(self.signature))
        self.parent.reactor.pub(url=self.parent.url, data=Envelope.create(merkle_sig))

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
            bc = BlockContender.create(signatures=self.signatures, nodes=self.merkle.nodes)
            self.parent.reactor.request(url=TestNetURLHelper.dealroute_url(Constants.Testnet.Masternode.InternalUrl),
                                        data=Envelope.create(bc))
            # once update confirmed from mn, transition to update state

    @recv(MerkleSignature)
    def recv_sig(self, sig: MerkleSignature):
        if self.validate_sig(sig):
            self.signatures.append(sig)
            self.check_majority()

    @recv_req(BlockDataRequest)
    def recv_blockdata_req(self, block_data: BlockDataRequest, id):
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


class DelegateUpdateState(DelegateBaseState): pass


## TESTING
# from functools import wraps
# import random
# P = 0.36
#
# def do_nothing(*args, **kwargs):
#     # print("!!! DOING NOTHING !!!\nargs: {}\n**kwargs: {}".format(args, kwargs))
#     print("DOING NOTHING")
#
# def sketchy_execute(prob_fail):
#     def decorate(func):
#         @wraps(func)
#         def wrapper(*args, **kwargs):
#             # print("UR BOY HAS INJECTED A SKETCH EXECUTE FUNC LOL LFG")
#             if random.random() < prob_fail:
#                 print("!!! not running func")
#                 return do_nothing(*args, **kwargs)
#             else:
#                 # print("running func")
#                 return func(*args, **kwargs)
#         return wrapper
#     return decorate
#
#
# class RogueMeta(type):
#     _OVERWRITES = ('route', 'route_req', 'route_timeout')
#
#     def __new__(cls, clsname, bases, clsdict):
#         clsobj = super().__new__(cls, clsname, bases, clsdict)
#
#         print("Rogue meta created with class name: ", clsname)
#         print("bases: ", bases)
#         print("clsdict: ", clsdict)
#         print("dir: ", dir(clsobj))
#
#         for name in dir(clsobj):
#             if name in cls._OVERWRITES:
#                 print("\n\n***replacing {} with sketchy executor".format(name))
#                 setattr(clsobj, name, sketchy_execute(P)(getattr(clsobj, name)))
#             else:
#                 print("skipping name {}".format(name))
#
#         return clsobj
## END TESTING


class Delegate(NodeBase):
    _INIT_STATE = DelegateBootState
    _STATES = [DelegateBootState, DelegateInterpretState, DelegateConsensusState, DelegateUpdateState]

    def __init__(self, url=None, signing_key=None, slot=0):
        if url is None and signing_key is None:
            node_info = Constants.Testnet.Delegates[slot]
            url = node_info['url']
            signing_key = node_info['sk']
        super().__init__(url=url, signing_key=signing_key)

        self.log = get_logger("Delegate-#{}".format(slot), auto_bg_val=slot)
        self.log.info("Delegate being created on slot {} with url {}".format(url, signing_key))

        # Shared between states
        self.pending_sigs, self.pending_txs = [], []  # TODO -- use real queue objects here

        # TODO -- add this as a property of the interpreter state, and implement functionality to pass data between
        # states on transition, i.e sm.transition(NextState, arg1='hello', arg2='let_do+it')
        # and the enter(...) of the next state should have these args
        self.interpreter = VanillaInterpreter()

        self.start()