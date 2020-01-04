from multiprocessing import Queue
from cilantro_ee.utils.lprocess import LProcess

from cilantro_ee.nodes.base import NodeBase
from cilantro_ee.nodes.masternode.transaction_batcher import TransactionBatcher
from cilantro_ee.nodes.masternode.block_aggregator import BlockAggregatorController
from cilantro_ee.nodes.masternode.webserver import start_webserver
from cilantro_ee.core.block_server import BlockServerProcess

import os, random

class Masternode(NodeBase):

    # This call should not block!
    def start_node(self):
        self.tx_queue = Queue()
        self.ipc_ip = 'mn-ipc-sock-' + str(os.getpid()) + '-' \
                       + str(random.randint(0, 2**32))
        self.ipc_port = 6967     # can be chosen randomly any open port

        self._start_web_server()
        if not os.getenv('MN_MOCK'):  # TODO @stu do we need this still? --davis
            self._start_batcher()
            self._start_block_server()
            self._start_block_agg()
            return 1
        else:
            self.log.warning("MN_MOCK env var is set! Not starting block aggregator or tx batcher.")
            return 0

    def _start_web_server(self):
        self.log.debug("Masternode starting REST server on port 8080")
        self.server = LProcess(target=start_webserver, name='WebServerProc', args=(self.tx_queue,))
        self.server.start()

    def _start_block_server(self):
        self.log.info("Masternode starting block server process")
        self.blk_server = LProcess(target=BlockServerProcess, name='BlockServer',
                                   kwargs={'signing_key': self.signing_key})
        self.blk_server.start()
        # todo - complete this - do we need socket_id? or just a port?

    def _start_batcher(self):
        # Create a worker to do transaction batching
        self.log.info("Masternode starting transaction batcher process")
        self.batcher = LProcess(target=TransactionBatcher, name='TxBatcherProc',
                                kwargs={'queue': self.tx_queue, 'ip': self.ip,
                                        'signing_key': self.signing_key,
                                        'ipc_ip': self.ipc_ip, 'ipc_port': self.ipc_port})
        self.batcher.start()


    def _start_block_agg(self):
        self.log.info("Masternode starting BlockAggregator Process")
        self.block_agg = LProcess(target=BlockAggregatorController,
                                  name='BlockAgg',
                                  kwargs={'ipc_ip': self.ipc_ip,
                                          'ipc_port': self.ipc_port,
                                          'signing_key': self.signing_key})
        self.block_agg.start()
