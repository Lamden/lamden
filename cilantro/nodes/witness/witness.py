from cilantro.nodes import NodeBase
from cilantro.constants.zmq_filters import WITNESS_MASTERNODE_FILTER, WITNESS_DELEGATE_FILTER
from cilantro.constants.ports import MN_TX_PUB_PORT
from cilantro.constants.testnet import *

from cilantro.protocol.states.state import State
from cilantro.protocol.states.decorators import input, enter_from_any, input_connection_dropped, input_socket_connected

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

    @input_socket_connected
    def socket_connected(self, socket_type: int, vk: str, url: str):
        if not hasattr(self, 'connected_masternodes'):
            self.connected_masternodes = set()
            self.connected_delegates = set()
        assert vk in VKBook.get_all(), "Connected to vk {} that is not present in VKBook.get_all()!!!".format(vk)
        key = vk + '_' + str(socket_type)
        self.log.spam("Delegate connected to vk {} with sock type {}".format(vk, socket_type))

        # TODO make less ugly pls
        if vk in VKBook.get_delegates():
            self.connected_delegates.add(key)
        elif vk in VKBook.get_masternodes():
            self.connected_masternodes.add(key)

        self.parent.transition(WitnessBootState)

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
        assert self.parent.verifying_key in WITNESS_MN_MAP, "Witness has vk {} that is not in WITNESS_MN_MAP {}!"\
            .format(self.parent.verifying_key, WITNESS_MN_MAP)

        # Sub to assigned Masternode
        mn_vk = WITNESS_MN_MAP[self.parent.verifying_key]
        self.log.notice("Witness with vk {} subscribing to masternode with vk {}".format(self.parent.verifying_key, mn_vk))
        self.parent.composer.add_sub(filter=WITNESS_MASTERNODE_FILTER, vk=mn_vk, port=MN_TX_PUB_PORT)

        # Create publisher socket
        self.parent.composer.add_pub(ip=self.parent.ip)

        # Once done setting up sockets, transition to RunState
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
