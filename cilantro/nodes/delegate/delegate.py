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
from cilantro.protocol.statemachine import State, input, input_timeout, input_request
from cilantro.protocol.statemachine.decorators import *
from cilantro.protocol.structures import MerkleTree
from cilantro.protocol.interpreters import VanillaInterpreter
from cilantro.protocol.wallets import ED25519Wallet
from cilantro.db import *
from cilantro.messages import TransactionBase, BlockContender, Envelope, MerkleSignature, \
    BlockDataRequest, BlockDataReply, NewBlockNotification


DelegateBootState = "DelegateBootState"
DelegateInterpretState = "DelegateInterpretState"
DelegateConsensusState = "DelegateConsensusState"


class Delegate(NodeBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Properties shared among all states (ie via self.parent.some_prop)
        self.pending_sigs, self.pending_txs = [], []  # TODO -- use real queue objects here

        # TODO -- add this as a property of the interpreter state, and implement functionality to pass data between
        # states on transition, i.e sm.transition(NextState, arg1='hello', arg2='let_do+it')
        self.interpreter = VanillaInterpreter()


class DelegateBaseState(State):

    def reset_attrs(self):
        pass

    @input(TransactionBase)
    def handle_tx(self, tx: TransactionBase):
        self.log.debug("Delegate not interpreting transactions, adding {} to queue".format(tx))
        self.parent.pending_txs.append(tx)
        self.log.debug("{} transactions pending interpretation".format(self.parent.pending_txs))

    @input(MerkleSignature)
    def handle_sig(self, sig: MerkleSignature):
        self.log.debug("Received signature with data {} but not in consensus, adding it to queue"
                       .format(sig._data))
        self.parent.pending_sigs.append(sig)

    @input(NewBlockNotification)
    def handle_new_block_notif(self, notif: NewBlockNotification):
        self.log.critical("got new block notification, but logic to handle it is not implement in subclass")
        raise NotImplementedError
        # TODO -- if we are in anything but consensus state, we need to go to update state


@Delegate.register_init_state
class DelegateBootState(DelegateBaseState):
    """
    Delegate Boot State consists of subscribing to all delegates/all witnesses as well as publishing to own url
    Also the delegate adds a router and dealer socket so masternode can identify which delegate is communicating
    """

    @enter_from_any
    def enter_any(self, prev_state):
        # Sub to other delegates
        for delegate_vk in VKBook.get_delegates():
            self.parent.composer.add_sub(vk=delegate_vk, filter=Constants.ZmqFilters.DelegateDelegate)

        # Sub to witnesses
        for witness_vk in VKBook.get_witnesses():
            self.parent.composer.add_sub(vk=witness_vk, filter=Constants.ZmqFilters.WitnessDelegate)

        # Pub on our own url
        self.parent.composer.add_pub(ip=self.parent.ip)

        # Add router socket
        self.parent.composer.add_router(ip=self.parent.ip)

        # Add dealer and sub socket for Masternodes
        for mn_vk in VKBook.get_masternodes():
            self.parent.composer.add_dealer(vk=mn_vk)
            self.parent.composer.add_sub(vk=mn_vk, filter=Constants.ZmqFilters.MasternodeDelegate)

        # Once done with boot state, transition to interpret
        self.parent.transition(DelegateInterpretState)


@Delegate.register_state
class DelegateInterpretState(DelegateBaseState):
    """
    Delegate interpret state has the delegate receive and interpret that transactions are valid according to the
    interpreter chosen. Once the number of transactions in the queue exceeds the size or a time interval is reached the
    delegate moves into consensus state
    """

    # TODO -- set this logic to only occur on enter from boot
    @enter_from_any
    def enter_from_any(self, prev_state):
        self.log.debug("Flushing pending tx queue of {} txs".format(len(self.parent.pending_txs)))
        for tx in self.parent.pending_txs:
            self.interpret_tx(tx)
        self.parent.pending_txs = []

        # (for debugging) TODO remove
        with DB() as db:
            r = db.execute('select * from state_meta')
            results = r.fetchall()
            self.log.critical("\n\n LATEST STATE INFO: {} \n\n".format(results))

    @exit_to_any
    def exit_any(self, next_state):
        # Flush queue if we are not leaving interpreting for consensus
        if next_state != DelegateConsensusState:
            self.log.critical("Delegate exiting interpreting for state {}, flushing queue".format(next_state))
            self.parent.interpreter.flush(update_state=False)

    @input(TransactionBase)
    def handle_tx(self, tx: TransactionBase):
        self.interpret_tx(tx=tx)

    def interpret_tx(self, tx: TransactionBase):
        self.parent.interpreter.interpret_transaction(tx)

        self.log.debug("Size of queue: {}".format(len(self.parent.interpreter.queue)))

        if self.parent.interpreter.queue_len >= Constants.Nodes.MaxQueueSize:
            self.log.info("Consensus time!")
            self.parent.transition(DelegateConsensusState)
        else:
            self.log.debug("Not consensus time yet, queue is only size {}/{}"
                           .format(self.parent.interpreter.queue_len, Constants.Nodes.MaxQueueSize))


@Delegate.register_state
class DelegateConsensusState(DelegateBaseState):
    """Consensus state is where delegates pass around a merkelized version of their transaction queues, publish them to
    one another, confirm the signature is valid, and then vote/tally the results"""
    NUM_DELEGATES = len(Constants.Testnet.Delegates)

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
        assert self.parent.interpreter.queue_len > 0, "Entered consensus state, but interpreter queue is empty!"

        # Merkle-ize transaction queue and create signed merkle hash
        all_tx = self.parent.interpreter.get_queue_binary()
        self.log.info("Delegate got tx from interpreter queue: {}".format(all_tx))
        self.merkle = MerkleTree(all_tx)
        self.merkle_hash = self.merkle.hash_of_nodes()
        self.log.info("Delegate got merkle hash {}".format(self.merkle_hash))
        self.signature = ED25519Wallet.sign(self.parent.signing_key, self.merkle_hash)

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
        assert self.merkle_hash is not None, "Cannot validate signature without our merkle hash set"
        self.log.debug("Validating signature: {}".format(sig))

        # Verify sender's vk exists in the state
        if sig.sender not in VKBook.get_delegates():
            self.log.critical("Received merkle sig from sender {} who was not registered nodes {}"
                              .format(sig.sender, VKBook.get_delegates()))
            return False
        # Verify we havne't received this signature already
        if sig in self.signatures:
            self.log.critical("Already received a signature from sender {}".format(sig.sender))
            return False

        # Below is just for debugging, so we can see if a signature cannot be verified
        if not sig.verify(self.merkle_hash, sig.sender):
            self.log.critical("Delegate could not verify signature: {}".format(sig))

        return sig.verify(self.merkle_hash, sig.sender)

    def check_majority(self):
        self.log.debug("delegate has {} signatures out of {} total delegates"
                       .format(len(self.signatures), self.NUM_DELEGATES))

        if len(self.signatures) >= Constants.Testnet.Majority:
            self.log.critical("\n\n\nDelegate in consensus!\n\n\n")
            self.in_consensus = True

            # Create BlockContender and send it to all Masternode(s)
            bc = BlockContender.create(signatures=self.signatures, nodes=self.merkle.nodes)
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
            self.log.critical("\n\n New block hash is the same as ours!!! \n\n")
            self.update_from_scratch(new_block_hash=notif.block_hash, new_block_num=notif.block_num)
            self.parent.transition(DelegateInterpretState)
        # Otherwise, our block is out of consensus and we must request the latest from a Masternode
        else:
            self.log.critical("\n\n New block hash {} does not match out own merkle_hash {} \n\n"
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
#             # print("UR BOY HAS INJECTED A SKETCH EXECUTE FUNC LOL GLHF")
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



