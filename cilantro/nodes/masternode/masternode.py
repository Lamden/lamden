from multiprocessing import Queue
from cilantro.utils.lprocess import LProcess
from cilantro.storage.vkbook import VKBook

from cilantro.nodes.base import NodeBase
from cilantro.nodes.masternode.transaction_batcher import TransactionBatcher
from cilantro.nodes.masternode.block_aggregator import BlockAggregator
from cilantro.nodes.masternode.master_store import MasterOps
from cilantro.nodes.masternode.webserver import start_webserver
import os


class Masternode(NodeBase):
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

    def start(self):
        self.tx_queue = Queue()
        self._start_web_server()

        if not os.getenv('MN_MOCK'):  # TODO @stu do we need this still? --davis
            self._start_batcher()
            self._start_block_agg()  # This call blocks!
        else:
            self.log.warning("MN_MOCK env var is set! Not starting block aggregator or tx batcher.")


    def _start_web_server(self):
        self.log.debug("Masternode starting REST server on port 8080")
        self.server = LProcess(target=start_webserver, name='WebServerProc', args=(self.tx_queue,))
        self.server.start()

    def _start_batcher(self):
        # Create a worker to do transaction batching
        self.log.info("Masternode starting transaction batcher process")
        self.batcher = LProcess(target=TransactionBatcher, name='TxBatcherProc',
                                kwargs={'queue': self.tx_queue, 'signing_key': self.signing_key,
                                        'ip': self.ip})
        self.batcher.start()

    def _start_block_agg(self):
        self.log.info("Masternode starting BlockAggregator Process")
        self.block_agg = BlockAggregator(ip=self.ip, manager=self.manager, name='BlockAgg')  # this call blocks
