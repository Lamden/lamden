from multiprocessing import Queue
from cilantro_ee.utils.lprocess import LProcess

from cilantro_ee.nodes.base import NodeBase
from cilantro_ee.nodes.masternode.transaction_batcher import TransactionBatcher
from cilantro_ee.nodes.masternode.block_aggregator import BlockAggregator
from cilantro_ee.nodes.masternode.webserver import start_webserver

import os, random


IPC_IP = 'masternode-ipc-sock'
IPC_PORT = 6967


class Masternode(NodeBase):

    # This call should not block!
    def start_node(self):
        self.tx_queue = Queue()
        self.ipc_ip = IPC_IP + '-' + str(os.getpid()) + '-' + str(random.randint(0, 2**32))

        self._start_web_server()
        if not os.getenv('MN_MOCK'):  # TODO @stu do we need this still? --davis
            self._start_batcher()
            self._start_block_agg()
            return 1
        else:
            self.log.warning("MN_MOCK env var is set! Not starting block aggregator or tx batcher.")
            return 0

    def _start_web_server(self):
        self.log.debug("Masternode starting REST server on port 8080")
        self.server = LProcess(target=start_webserver, name='WebServerProc', args=(self.tx_queue,))
        self.server.start()

    def _start_batcher(self):
        # Create a worker to do transaction batching
        self.log.info("Masternode starting transaction batcher process")
        self.batcher = LProcess(target=TransactionBatcher, name='TxBatcherProc',
                                kwargs={'queue': self.tx_queue, 'signing_key': self.signing_key,
                                        'ip': self.ip, 'ipc_ip': self.ipc_ip, 'ipc_port': IPC_PORT})
        self.batcher.start()

    def _start_block_agg(self):
        self.log.info("Masternode starting BlockAggregator Process")
        self.block_agg = LProcess(target=BlockAggregator,  name='BlockAgg', kwargs={'ip': self.ip, 'ipc_ip': self.ipc_ip, 'ipc_port': IPC_PORT, 'signing_key': self.signing_key, 'name': 'BlockAgg'})
        self.block_agg.start()
