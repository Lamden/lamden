from cilantro.nodes import NodeBase
from cilantro.constants.zmq_filters import WITNESS_MASTERNODE_FILTER, WITNESS_DELEGATE_FILTER
from cilantro.constants.ports import MN_TX_PUB_PORT

from cilantro.protocol.states.state import State
from cilantro.protocol.states.decorators import input, enter_from_any, input_connection_dropped

from cilantro.messages.transaction.base import TransactionBase
from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.transaction.ordering import OrderingContainer
from cilantro.messages.signals.kill_signal import KillSignal

from cilantro.storage.db import VKBook

"""
    Witness

    Witnesses exist primarily to check the validity of proofs of transactions sent out by TESTNET_MASTERNODES.
    They subscribe to TESTNET_MASTERNODES on the network, confirm the hashcash style proof provided by the sender is valid, and
    then go ahead and pass the transaction along to TESTNET_DELEGATES to include in a block. They will also facilitate
    transactions that include stake reserves being spent by users staking on the network.
"""


class Witness(NodeBase):
    pass


class WitnessBaseState(State):

    @input(KillSignal)
    def handle_kill_sig(self, msg: KillSignal):
        # TODO - make sure this is secure (from a KillSignal)
        self.log.important("Node got received remote kill signal from network!")
        self.parent.teardown()

    @input_connection_dropped
    def conn_dropped(self, vk, ip):
        self.log.important2('({}:{}) has dropped'.format(vk, ip))
        pass

    @input(TransactionBase)
    def recv_tx(self, tx: TransactionBase, envelope: Envelope):
        self.log.error("Witness not configured to recv tx: {} with env {}".format(tx, envelope))

    @input(OrderingContainer)
    def recv_ordered_tx(self, tx: OrderingContainer, envelope: Envelope):
        self.log.error("Witness not configured to recv ordered tx: {} with env {}".format(tx, envelope))


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
            self.parent.composer.add_sub(filter=WITNESS_MASTERNODE_FILTER, vk=mn_vk, port=MN_TX_PUB_PORT)

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

    @input(OrderingContainer)
    def recv_ordered_tx(self, tx: OrderingContainer, envelope: Envelope):
        self.log.spam("witness got tx: {}, with env {}".format(tx, envelope))
        self.parent.composer.send_pub_env(envelope=envelope, filter=WITNESS_DELEGATE_FILTER)
