"""
    Masternode
    These are the entry points to the blockchain and pass messages on throughout the system. They are also the cold
    storage points for the blockchain once consumption is done by the network.

    They have no say as to what is 'right,' as governance is ultimately up to the network. However, they can monitor
    the behavior of nodes and tell the network who is misbehaving.
"""

from cilantro.protocol.states.decorators import *
from cilantro.protocol.states.state import State

from multiprocessing import Queue
from cilantro.utils.lprocess import LProcess
from cilantro.storage.vkbook import VKBook

from cilantro.nodes.base import NodeBase
from cilantro.nodes.base import NewNodeBase
from cilantro.nodes.masternode.webserver import start_webserver
from cilantro.nodes.masternode.transaction_batcher import TransactionBatcher
from cilantro.nodes.masternode.block_aggregator import BlockAggregator

import os


class Masternode(NewNodeBase):

    def start(self):
        self._start_web_server()

        if not os.getenv('MN_MOCK'):
            self._start_batcher()
            self._start_block_agg()
        else:
            self.log.warning("MN_MOCK env var is set! Not starting block aggregator or tx batcher.")

    def _start_web_server(self):
        self.log.debug("Masternode starting REST server on port 8080")
        self.tx_queue = q = Queue()
        self.server = LProcess(target=start_webserver, name='WebServerProc', args=(q,))
        self.server.start()

    def _start_batcher(self):
        # Create a worker to do transaction batching
        self.log.info("Masternode starting transaction batcher process")
        self.batcher = LProcess(target=TransactionBatcher, name='TxBatcherProc',
                                kwargs={'queue': q, 'signing_key': self.signing_key,
                                        'ip': self.ip})
        self.batcher.start()

    def _start_block_agg(self):
        # # TODO Start the BlockAggregator in this process by passing in our SocketManager instead of spinning up an LProc
        self.log.info("Masternode starting BlockAggregator Process")
        self.block_agg_proc = LProcess(target=BlockAggregator,
                                       kwargs={'ip': self.ip, 'signing_key': self.signing_key},
                                       name='BlockAggProc')
        self.block_agg_proc.start()


# class MNBaseState(State):
#     pass
#
#
# @Masternode.register_init_state
# class MNBootState(MNBaseState):
#
#     # For dev, we require all nodes to be online. IRL this could perhaps be 2/3 node for each role  --davis
#     REQ_MNS = len(VKBook.get_masternodes())
#     REQ_DELS = len(VKBook.get_delegates())
#     REQ_WITS = len(VKBook.get_witnesses())
#
#     @timeout_after(120)  # TODO make this a constants
#     def boot_timeout(self):
#         err = "Masternode could not connect to required qourum!\nMn set: {}\nDelegate set: {}\nWitness " \
#               "set: {}".format(self.online_mns, self.online_dels, self.online_wits)
#         self.log.fatal(err)
#         raise Exception(err)
#
#     def reset_attrs(self):
#         self.online_mns, self.online_dels, self.online_wits = set(), set(), set()
#
#     # TODO subscribe to node_online events from the delegates/masternodes
#     def quorum_reached(self) -> bool:
#         return (self.REQ_MNS <= len(self.online_mns)) and (self.REQ_DELS <= len(self.online_dels)) and \
#                (self.REQ_WITS <= len(self.online_wits))
#
#     def check_qourum(self):
#         if self.quorum_reached():
#             self.log.info("Quorum reached! Transitioning to run state")
#             self.parent.transition(MNRunState)
#         else:
#             self.log.debugv("Quorum not reached yet.")
#
#     # TODO link this function up with overlay events that monitor new nodes coming online
#     # But we also need to include nodes that are ALREADY online at the time of booting
#     def add_online_vk(self, vk: str):
#         # Dev check (maybe dont do this IRL)
#         assert vk in VKBook.get_all(), "VK {} not in VKBook vks {}".format(vk, VKBook.get_all())
#         self.log.debugv("Adding vk {} to online nodes".format(vk))
#
#         if vk in VKBook.get_witnesses():
#             self.online_wits.add(vk)
#         if vk in VKBook.get_delegates():
#             self.online_dels.add(vk)
#         if vk in VKBook.get_masternodes():
#             self.online_mns.add(vk)
#
#         self.check_qourum()
#
#     @enter_from_any
#     def enter_any(self, prev_state):
#         # TODO seed online node set with nodes who are already available/online. Ping them or something.
#         self.check_qourum()
#
#
# @Masternode.register_state
# class MNRunState(MNBaseState):
#     def reset_attrs(self):
#         pass
#
#     def start_batcher(self):
#         # Create a worker to do transaction batching
#         self.log.debug("Masternode starting transaction batcher process")
#         self.parent.batcher = LProcess(target=TransactionBatcher, name='TxBatcherProc',
#                                        kwargs={'queue': q, 'signing_key': self.parent.signing_key,
#                                                'ip': self.parent.ip})
#         self.parent.batcher.start()
#
#     def start_block_agg(self):
#         # Start the BlockAggregator in this process
#         self.log.notice("Masternode starting BlockAggregator Process")
#         self.block_agg_proc = LProcess(target=BlockAggregator,
#                                        kwargs={'ip': self.parent.ip, 'signing_key': self.parent.signing_key},
#                                        name='BlockAggProc')
#         self.block_agg_proc.start()
#
#     @enter_from_any
#     def enter_any(self):
#         # Create and start web server
#         self.log.debug("Masternode starting REST server on port 8080")
#         self.parent.tx_queue = q = Queue()
#         self.parent.server = LProcess(target=start_webserver, name='WebServerProc', args=(q,))
#         self.parent.server.start()
#
#         # TODO -- use THIS process for the block aggregator. No need to have it idle, twiddling its thumbs.
#         if not os.getenv('MN_MOCK'):
#             self.start_batcher()
#             self.start_block_agg()
#         else:
#             self.log.warning("MN_MOCK env var is set! Not starting block aggregator or tx batcher.")
#
#

