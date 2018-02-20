from cilantro.serialization import JSONSerializer
from cilantro.proofs.pow import SHA3POW, POW
from cilantro.networking.constants import MAX_QUEUE_SIZE, QUEUE_AUTO_FLUSH_TIME
from cilantro.db.delegate.transaction_queue_driver import TransactionQueueDriver
from cilantro.networking import BaseNode
from cilantro.interpreters.basic_interpreter import BasicInterpreter
from cilantro.transactions.testnet import TestNetTransaction
import time
import sys
import requests
import asyncio
if sys.platform != 'win32':
    pass


"""
    Delegates

    Delegates are the "miners" of the Cilantro blockchain in that they opportunistically bundle up transactions into 
    blocks and are rewarded with TAU for their actions. They receive approved transactions from delegates and broadcast
    blocks based on a 1 second or 10,000 transaction limit per block. They should be able to connect/drop from the 
    network seamlessly as well as coordinate blocks amongst themselves.
    
     Delegate logic:   
        Step 1) Delegate takes 10k transactions from witness and forms a block
        Step 2) Block propagates across the network to other delegates
        Step 3) Delegates pass around in memory DB hash to confirm they have the same blockchain state
        Step 4) Next block is mined and process repeats

        zmq pattern: subscribers (delegates) need to be able to communicate with one another. this can be achieved via
        a push/pull pattern where all delegates push their state to sink that pulls them in, but this is centralized.
        another option is to use ZMQ stream to have the tcp sockets talk to one another outside zmq
"""


class Delegate(BaseNode):
    def __init__(self, host='127.0.0.1', sub_port='8888', serializer=JSONSerializer, hasher=POW, pub_port='7878'):
        BaseNode.__init__(self, host=host, sub_port=sub_port, pub_port=pub_port, serializer=serializer)
        self.hasher = hasher
        self.last_flush_time = time.time()
        self.queue = TransactionQueueDriver()
        self.interpreter = BasicInterpreter()
        self.timer_flag = None

        # asyncio.ensure_future(self.flush_time())  # fire and forget function that returns after flush time (1 second)

    async def process_transaction(self, data: bytes=None):
        """
        Processes a transaction from witness. This first feeds it through the interpreter, and if
        no errors are thrown, then adds the transaction to the queue. Then flushes queue to perform consensus.
        :param data: The raw transaction data, assumed to be in byte format
        :return:
        """
        d, tx = None, None

        try:
            d = self.serializer.deserialize(data)
            TestNetTransaction.validate_tx_fields(d)
            tx = TestNetTransaction.from_dict(d)
            self.interpreter.interpret_transaction(tx)
        except Exception as e:
            print("Error in delegate process transaction: {}".format(e))
            return {'error_status': 'Delegate error processing transaction: {}'.format(e)}

        print('queueing tx : {}'.format(d))

        self.queue.enqueue_transaction(tx.payload['payload'])  # put transaction into queue

        asyncio.ensure_future(self.flush_time())  # fire and forget function that returns after flush time (1 second)

        self.timer_flag = 0 #  blocking??? :/
        while not self.timer_flag:
            if self.queue.queue_size() > MAX_QUEUE_SIZE:
                print('queue exceeded max size, flushing queue')
                self.perform_consensus()
            else:
                print('time since last queue flush exceeded, flushing queue')
                self.perform_consensus()

        return {'success': 'delegate processed transaction: {}'.format(d)}

    async def handle_req(self, data: bytes=None):
        return await self.process_transaction(data=data)

    def perform_consensus(self):
        if self.queue.queue_size() <= 0:
            print("queue is empty, doing nothing")

        print('delegate performing consensus...')

        # TODO -- consensus

        # Package block for transport
        all_tx = self.queue.dequeue_all()

        # BELOW LOGIC MOVED TO MASTERNODE
        # h = hashlib.sha3_256()
        # h.update(self.serializer.serialize(all_tx))
        # block = {'block': all_tx, 'hash': h.hexdigest()}

        block = {'transactions': all_tx}

        self.last_flush_time = time.time()
        self.post_block(self.serializer.serialize(block))

    def post_block(self, block: bytes):
        print("Delegate posting block to masternode\nBlock binary: {}".format(block))
        r = requests.post("http://127.0.0.1:8080/add_block", data=block)
        if r.status_code == 200:
            print('Delegate succesfully posted block to Masternode')
        else:
            print("Delegate had problem posting block to Masternode (status code={})".format(r.status_code))

    async def flush_time(self):
        print('waiting a second')
        await asyncio.sleep(QUEUE_AUTO_FLUSH_TIME)
        print('second over')
        self.timer_flag = 1
