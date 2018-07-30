from cilantro.nodes import NodeBase
from cilantro.protocol.statemachine.state import State
from cilantro.messages.transaction.base import TransactionBase
from cilantro.messages.envelope.envelope import Envelope
from cilantro.protocol.statemachine.decorators import *
from cilantro.db.db import VKBook
from cilantro.constants.zmq_filters import witness_masternode, witness_delegate


"""
    Witness

    Witnesses exist primarily to check the validity of proofs of transactions sent out by masternodes.
    They subscribe to masternodes on the network, confirm the hashcash style proof provided by the sender is valid, and
    then go ahead and pass the transaction along to delegates to include in a block. They will also facilitate
    transactions that include stake reserves being spent by users staking on the network.
"""


class Witness(NodeBase):
    pass


class WitnessBaseState(State):
    @input(TransactionBase)
    def recv_tx(self, tx: TransactionBase, envelope: Envelope):
        self.log.error("Witness not configured to recv tx: {} with env {}".format(tx, envelope))


@Witness.register_init_state
class WitnessBootState(WitnessBaseState):
    """
    Witness boot state has witness sub to masternode and establish a pub socket and router socket
    """

    def reset_attrs(self):
        pass

    @enter_from_any
    def enter(self, prev_state):

        # Sub to Masternodes
        for mn_vk in VKBook.get_masternodes():
            self.log.debug("Subscribes to MN with vk: {}".format(mn_vk))
            self.parent.composer.add_sub(filter=witness_masternode, vk=mn_vk)

        # Create publisher socket
        self.parent.composer.add_pub(ip=self.parent.ip)

        # Once done setting up sockets, transition to RunState
        self.parent.transition(WitnessRunState)

    def run(self):
        self.parent.transition(WitnessRunState)


@Witness.register_state
class WitnessRunState(WitnessBaseState):
    """
    Witness run state has the witness receive transactions sent from masternode
    """

    def reset_attrs(self):
        pass

    @input(TransactionBase)
    def recv_tx(self, tx: TransactionBase, envelope: Envelope):
        self.log.debug("witness got tx: {}, with env {}".format(tx, envelope))  # debug line, remove later
        self.parent.composer.send_pub_env(envelope=envelope, filter=witness_delegate)
        self.log.debug("witness published tx")  # debug line, remove later

