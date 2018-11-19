from cilantro.nodes.base import NodeBase
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
from cilantro.utils.hasher import Hasher

import zmq, asyncio

"""
    Witness

    Witnesses exist primarily to check the validity of proofs of transactions sent out by TESTNET_MASTERNODES.
    They subscribe to TESTNET_MASTERNODES on the network, confirm the hashcash style proof provided by the sender is valid, and
    then go ahead and pass the transaction along to TESTNET_DELEGATES to include in a block. They will also facilitate
    transactions that include stake reserves being spent by users staking on the network.
"""


class Witness(NodeBase):
    def __init__(self, *args, **kwargs):
        # Put all variables shared between states here
        self.tasks = []
        self.sub, self.pub = None, None

        # Call super after since we need to define these variables before we kick off into boot state
        # this is shitty and confusing i am v sorry --davis
        super().__init__(*args, **kwargs)



class WitnessBaseState(State):
    pass

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

    def _create_sub_socket(self):
        # Sub to assigned Masternode
        mn_vk = WITNESS_MN_MAP[self.parent.verifying_key]
        self.log.notice("Witness w/ vk {} subscribing to MN with vk {}".format(self.parent.verifying_key, mn_vk))

        self.parent.sub = self.parent.manager.create_socket(socket_type=zmq.SUB, name='MN-Subscriber', secure=True)
        self.parent.sub.connect(vk=mn_vk, port=MN_TX_PUB_PORT)
        self.parent.sub.setsockopt(zmq.SUBSCRIBE, WITNESS_MASTERNODE_FILTER.encode())

    def _create_pub_socket(self):
        # Connect PUB socket to SBBs
        self.parent.pub = self.parent.manager.create_socket(socket_type=zmq.PUB, name='SBB-Publisher', secure=True)

        mn_vk = WITNESS_MN_MAP[self.parent.verifying_key]
        mn_idx = VKBook.get_masternodes().index(mn_vk)
        port = SBB_PORT_START + mn_idx

        self.log.notice("Witness /w vk {} BINDING sub socket to port {}".format(self.parent.verifying_key, port))

        for delegate_vk in VKBook.get_delegates():
            self.parent.pub.connect(vk=delegate_vk, port=port)
            time.sleep(1)

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

        self.log.important("Witness starting main event loop!")
        self.parent.loop.run_until_complete(asyncio.gather(*self.parent.tasks))

    def handle_sub_msg(self, frames):
        # Deserialize to check envelope date. This might be unnecessary in prod
        env = Envelope.from_bytes(frames[-1])
        assert type(env.message) is TransactionBatch, "Witness expected to receive only TransactionBatch messages, but " \
                                                      "got unknown type {}".format(type(env.message))
        self.log.info(
            "Witness sending out transaction batch with input hash {} and {} transactions".format(Hasher.hash(env), len(
                env.message.transactions)))
        self.parent.pub.send_multipart([b'', frames[-1]])

