from cilantro.nodes.base import NewNodeBase
from cilantro.constants.zmq_filters import WITNESS_MASTERNODE_FILTER, WITNESS_DELEGATE_FILTER
from cilantro.constants.ports import MN_TX_PUB_PORT, SBB_PORT_START
from cilantro.constants.testnet import *

from cilantro.protocol.states.state import State
from cilantro.protocol.states.decorators import input, enter_from_any, input_connection_dropped, input_socket_connected
from cilantro.protocol.reactor.socket_manager import SocketManager

from cilantro.messages.transaction.base import TransactionBase
from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.transaction.ordering import OrderingContainer
from cilantro.messages.transaction.batch import TransactionBatch
from cilantro.messages.signals.kill_signal import KillSignal

from cilantro.storage.db import VKBook

import zmq, asyncio

"""
    Witness

    Witnesses exist primarily to check the validity of proofs of transactions sent out by TESTNET_MASTERNODES.
    They subscribe to TESTNET_MASTERNODES on the network, confirm the hashcash style proof provided by the sender is valid, and
    then go ahead and pass the transaction along to TESTNET_DELEGATES to include in a block. They will also facilitate
    transactions that include stake reserves being spent by users staking on the network.
"""


class Witness(NewNodeBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Put all variables shared between states here
        self.sub, self.pub = None, None


class WitnessBaseState(State):

    @input(KillSignal)
    def handle_kill_sig(self, msg: KillSignal):
        # TODO - make sure this is secure (from a KillSignal)
        self.log.important("Node got received remote kill signal from network!")
        self.parent.teardown()

    @input_socket_connected
    def socket_connected(self, socket_type: int, vk: str, url: str):
        self.log.warning("Witness state {} not configured to handle socket_connected event".format(type(self)))

    @input_connection_dropped
    def conn_dropped(self, vk, ip):
        self.log.important2('vk {} with ip {} has dropped'.format(vk, ip))

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
        assert self.parent.verifying_key in WITNESS_MN_MAP, "Witness has vk {} that is not in WITNESS_MN_MAP {}!" \
            .format(self.parent.verifying_key, WITNESS_MN_MAP)

        self._create_sub_socket()
        self._create_pub_socket()

        self.parent.transition(WitnessRunState)

        # Create a publisher socket to each delegate SBB process
        # self.parent.composer.add_pub(ip=self.parent.ip)

        # Sub to assigned Masternode
        # mn_vk = WITNESS_MN_MAP[self.parent.verifying_key]
        # self.log.notice("Witness with vk {} subscribing to masternode with vk {}".format(self.parent.verifying_key, mn_vk))
        # self.parent.composer.add_sub(filter=WITNESS_MASTERNODE_FILTER, vk=mn_vk, port=MN_TX_PUB_PORT)

        # Once done setting up sockets, transition to RunState
        # self.parent.transition(WitnessRunState)

    def _create_sub_socket(self):
        # Sub to assigned Masternode
        self.parent.sub = self.parent.manager.create_socket(socket_type=zmq.SUB, name='MN-Subscriber')

        mn_vk = WITNESS_MN_MAP[self.parent.verifying_key]
        self.log.notice("Witness w/ vk {} subscribing to MN with vk {}".format(self.parent.verifying_key, mn_vk))
        # self.parent.composer.add_sub(filter=WITNESS_MASTERNODE_FILTER, vk=mn_vk, port=MN_TX_PUB_PORT)
        self.parent.sub.connect(vk=mn_vk, port=MN_TX_PUB_PORT)

    def _create_pub_socket(self):
        # Connect PUB socket to SBBs
        self.parent.pub = self.parent.manager.create_socket(socket_type=zmq.PUB, name='SBB-Publisher')

        mn_vk = WITNESS_MN_MAP[self.parent.verifying_key]
        mn_idx = VKBook.get_masternodes().find(mn_vk)
        port = SBB_PORT_START + mn_idx

        self.log.notice("Witness /w vk {} BINDING sub socket to port {}".format(self.parent.verifying_key, port))

        for delegate_vk in VKBook.get_delegates():
            self.parent.pub.connect(vk=delegate_vk, port=port)

@Witness.register_state
class WitnessRunState(WitnessBaseState):
    """
    Witness run state has the witness receive transactions sent from masternode
    """

    def reset_attrs(self):
        pass

    @enter_from_any
    def enter(self, prev_state):
        assert self.parent.sub, "Sub socket should have been created"
        assert self.parent.pub, "Pub socket should have been created"

        self.parent.tasks.append(self.parent.sub.add_handler(handler_func=self.handle_sub_msg))
        self.loop.run_until_complete(asyncio.gather(*self.tasks))

    def handle_sub_msg(self, frames):
        self.log.spam("Witness got SUB data with frames {}".format(frames))
        # Deserialize to check envelope date. This might be unnecessary in prod
        env = Envelope.from_bytes(frames[-1])
        self.log.debugv("Witness got SUB data with envelope {}".format(env))
        assert type(env.message) is TransactionBatch, "Witness expected to receive only TransactionBatch messages, but " \
                                                      "got unknown type {}".format(type(env.message))

        self.parent.pub.send_multipart([b'', frames[-1]])

    # @input(OrderingContainer)
    # def recv_ordered_tx(self, tx: OrderingContainer, envelope: Envelope):
    #     self.log.spam("witness got tx: {}, with env {}".format(tx, envelope))
    #     raise Exception("Sending OrderingContainers directly to Witnesses should be deprecated! "
    #                     "We should be sending TransactionBatch messages")
    #     # self.parent.composer.send_pub_env(envelope=envelope, filter=WITNESS_DELEGATE_FILTER)

    # @input(TransactionBatch)
    # def recv_tx_batch(self, batch: TransactionBatch, envelope: Envelope):
    #     self.log.important("Witness got TransactionBatch {}".format(batch))  # TODO change log level once confident
    #
    #     # TODO send this using the appropriate sub_block_builder port and filter
    #     self.parent.composer.send_pub_env(envelope=envelope, filter=WITNESS_DELEGATE_FILTER)
