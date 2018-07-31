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

from cilantro.nodes import NodeBase
from cilantro.protocol.interpreter import SenecaInterpreter
from cilantro.storage.db import VKBook

from cilantro.protocol.states.decorators import input, enter_from_any
from cilantro.protocol.states.state import State

from cilantro.messages.transaction.base import TransactionBase
from cilantro.messages.consensus.merkle_signature import MerkleSignature
from cilantro.messages.transaction.ordering import OrderingContainer
from cilantro.messages.block_data.transaction_data import TransactionReply, TransactionRequest
from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.block_data.block_metadata import BlockMetaDataReply, NewBlockNotification

from cilantro.constants.zmq_filters import delegate_delegate, witness_delegate, masternode_delegate
from cilantro.protocol.interpreter import SenecaInterpreter
from cilantro.storage.blocks import BlockStorageDriver
from collections import deque

import time

DelegateBootState = "DelegateBootState"
DelegateInterpretState = "DelegateInterpretState"
DelegateConsensusState = "DelegateConsensusState"
DelegateCatchupState = "DelegateCatchupState"


class Delegate(NodeBase):
    """
    Here we define 'global' properties shared among all Delegate states. Within a Delegate state, 'self.parent' refers
    to this instance.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Properties shared among all states (ie via self.parent.some_prop)
        self.pending_sigs, self.pending_txs = deque(), deque()
        self.interpreter = SenecaInterpreter()
        self.current_hash = BlockStorageDriver.get_latest_block_hash()


class DelegateBaseState(State):

    def reset_attrs(self):
        pass

    @input(OrderingContainer)
    def handle_tx(self, tx: OrderingContainer):
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
        self.log.critical("Delegate got new block notification with hash {}\nprev_hash {}]\nand our current hash = {}"
                          .format(notif.block_hash, notif.prev_block_hash, self.parent.current_hash))
        self.parent.transition(DelegateCatchupState)

    @input(TransactionReply)
    def handle_tx_reply(self, reply: TransactionReply, envelope: Envelope):
        self.log.debug("Delegate current state {} not configured to handle"
                        "transaction replies".format(self))

    @input(TransactionRequest)
    def handle_tx_request(self, request: TransactionRequest):
        self.log.debug("Delegate current state {} not configured to handle"
                        "transaction requests".format(self))

    @input(BlockMetaDataReply)
    def handle_blockmeta_reply(self, reply: BlockMetaDataReply):
        self.log.debug("Delegate current state {} not configured to handle block"
                       "meta replies".format(self))


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
            # Do not sub to ourself
            if delegate_vk == self.parent.verifying_key:
                continue

            self.parent.composer.add_sub(vk=delegate_vk, filter=delegate_delegate)

        # Sub to witnesses
        for witness_vk in VKBook.get_witnesses():
            self.parent.composer.add_sub(vk=witness_vk, filter=witness_delegate)

        # Pub on our own url
        self.parent.composer.add_pub(ip=self.parent.ip)

        # Add router socket
        self.parent.composer.add_router(ip=self.parent.ip)

        # Add dealer and sub socket for Masternodes
        for mn_vk in VKBook.get_masternodes():
            self.parent.composer.add_dealer(vk=mn_vk)
            self.parent.composer.add_sub(vk=mn_vk, filter=masternode_delegate)

        # Sleep for a bit while the daemon sets up these sockets TODO find a more reactive solution
        time.sleep(16)

        # Once done with boot state, transition to catchup
        self.parent.transition(DelegateCatchupState)


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
