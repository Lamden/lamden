from cilantro.nodes.base import NodeBase, NodeTypes
from cilantro.constants.zmq_filters import *
from cilantro.constants.ports import MN_TX_PUB_PORT, SBB_PORT_START
from cilantro.constants.testnet import *

from cilantro.protocol.reactor.socket_manager import SocketManager

from cilantro.messages.transaction.base import TransactionBase
from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.transaction.ordering import OrderingContainer
from cilantro.messages.transaction.batch import TransactionBatch
from cilantro.messages.signals.kill_signal import KillSignal

from cilantro.storage.vkbook import VKBook
from cilantro.utils.hasher import Hasher

import zmq, asyncio, time


class Witness(NodeBase):

    def start(self):
        self.tasks = []

        self._create_sub_socket()
        self._create_pub_socket()

        self.loop.run_until_complete(asyncio.gather(*self.tasks))

    def _create_sub_socket(self):
        # Sub to assigned Masternode
        mn_vk = WITNESS_MN_MAP[self.verifying_key]
        self.log.notice("Witness w/ vk {} subscribing to MN with vk {}".format(self.verifying_key, mn_vk))

        self.sub = self.manager.create_socket(socket_type=zmq.SUB, name='MN-Subscriber', secure=True)
        self.sub.connect(vk=mn_vk, port=MN_TX_PUB_PORT)
        self.sub.setsockopt(zmq.SUBSCRIBE, WITNESS_MASTERNODE_FILTER.encode())

        self.tasks.append(self.sub.add_handler(self._handle_sub_msg))

    def _create_pub_socket(self):
        # Connect PUB socket to SBBs
        self.pub = self.manager.create_socket(socket_type=zmq.PUB, name='SBB-Publisher', secure=True)

        mn_vk = WITNESS_MN_MAP[self.verifying_key]
        mn_idx = VKBook.get_masternodes().index(mn_vk)
        port = SBB_PORT_START + mn_idx

        for delegate_vk in VKBook.get_delegates():
            self.log.info("Witness connecting PUB socket to vk {} on port {}".format(delegate_vk, port))
            self.pub.connect(vk=delegate_vk, port=port)

    def _handle_sub_msg(self, frames):
        # Deserialize to check envelope date. This might be unnecessary in prod
        env = Envelope.from_bytes(frames[-1])

        if not env.is_from_group(NodeTypes.MN):
            self.log.warning("Received envelope from sender {} that is not a masternode!".format(env.sender))
            return
        assert type(env.message) is TransactionBatch, "Witness expected to receive only TransactionBatch messages, but " \
                                                      "got unknown type {}".format(type(env.message))

        self.log.info("Witness sending out transaction batch with input hash {} and {} transactions"
                      .format(Hasher.hash(env), len(env.message.transactions)))
        self.pub.send_multipart([DEFAULT_FILTER.encode(), frames[-1]])
