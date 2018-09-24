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

from cilantro.nodes.base import NewNodeBase
from cilantro.nodes.masternode.webserver import start_webserver
from cilantro.nodes.masternode.transaction_batcher import TransactionBatcher
from cilantro.nodes.masternode.block_aggregator import BlockAggregator


class Masternode(NewNodeBase):
    pass


class MNBaseState(State):
    pass


@Masternode.register_init_state
class MNBootState(MNBaseState):

    def reset_attrs(self):
        pass

    @enter_from_any
    def enter_any(self, prev_state):
        # TODO -- get quorum before we transition to RunState

        self.parent.transition(MNRunState)


@Masternode.register_state
class MNRunState(MNBaseState):
    def reset_attrs(self):
        pass

    @enter_from_any
    def enter_any(self):
        # Create and start web server
        self.log.debug("Masternode creating REST server on port 8080")
        self.parent.tx_queue = q = Queue()
        self.parent.server = LProcess(target=start_webserver, args=(q,))
        self.parent.server.start()

        # Create a worker to do transaction batching
        self.log.debug("Masternode creating transaction batcher process")
        self.parent.batcher = LProcess(target=TransactionBatcher,
                                       kwargs={'queue': q, 'signing_key': self.parent.signing_key,
                                               'ip': self.parent.ip})
        self.parent.batcher.start()

        # Start the BlockAggregator in this process
        self.block_agg = BlockAggregator(ip=self.parent.ip, signing_key=self.parent.signing_key)


