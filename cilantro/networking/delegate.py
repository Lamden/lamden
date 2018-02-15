import asyncio
import zmq
from zmq.asyncio import Context
from cilantro.serialization import JSONSerializer
from cilantro.proofs.pow import SHA3POW
from cilantro.networking.constants import MAX_QUEUE_SIZE
from cilantro.db.transaction_queue_db import TransactionQueueDB
from cilantro.interpreters.basic_interpreter import BasicInterpreter
from cilantro.transactions.testnet import TestNetTransaction
from cilantro.serialization import PickleSerializer
import time
import sys

if sys.platform != 'win32':
    import uvloop


"""
    Delegates

    Delegates are the "miners" of the Cilantro blockchain in that they opportunistically bundle up transactions into 
    blocks and are rewarded with TAU for their actions. They receive approved transactions from delegates and broadcast
    blocks based on a 1 second or 10,000 transaction limit per block. They should be able to connect/drop from the 
    network seamlessly as well as establish consensus amongst themselves.
    
     Delegate logic:
        Step 0) Delegate receives POW-verified tx and interprets it to make sure tx is valid. If so add to Queue   
        Step 1) Delegate pops 10k transactions (stamps, atomic transactions, etc) from Queue into a block
        Step 2) Serialize block (pickle)
        Step 2) Hash pickled object in order to generate unique block fingerprint 
        Step 3) Delegates pass around their hash to confirm they have the same blockchain state via Harmony
         message pattern
        Step 4) Block is sent back to masternode for cold storage
        Step 5) Next block is mined and process repeats

        zmq pattern: Delegates will act according to the harmony pattern to seamlessly pass messages amongst themselves
        Upon consensus block formation masternode will PULL block info from random delegate
"""


class Delegate(object):
    def __init__(self, host='127.0.0.1', sub_port='7777', serializer=JSONSerializer, hasher=SHA3POW):
        self.host = host
        self.sub_port = sub_port
        self.serializer = serializer
        self.hasher = hasher
        self.sub_url = 'tcp://{}:{}'.format(self.host, self.sub_port)

        self.ctx = Context()
        self.delegate_sub = self.ctx.socket(socket_type=zmq.SUB)

        self.queue = TransactionQueueDB()
        self.interpreter = BasicInterpreter()

        self.loop = None

        self.blockserializer = PickleSerializer
        self.block = None

        self.dealer_socket = self.ctx.socket(socket_type=zmq.DEALER)
        self.dealer_port = '5555'
        self.dealer_url = 'tcp://{}:{}'.format(self.host, self.dealer_port)

        self.router_socket = self.ctx.socket(socket_type=zmq.ROUTER)
        self.router_port = '6666'
        self.router_url = 'tcp://{}:{}'.format(self.host, self.router_port)

    def start_async(self):
        self.loop = asyncio.get_event_loop() # set uvloop here
        self.loop.run_until_complete(self.recv())

    async def receive_witness_msg(self):
        """Main entry point for delegate socket to receive messages from witness socket"""
        self.delegate_sub.connect(self.sub_url)
        self.delegate_sub.setsockopt(zmq.SUBSCRIBE, b'')

        while True:
            msg_count = 0
            msg = await self.delegate_sub.recv()
            print('received', msg)
            msg_count += 1
            if self.delegate_time() or msg_count == 10000: # conditions for delegate logic go here.
                pass

    async def delegate_time(self):
        """Conditions to check that 1 second has passed"""
        start_time = time.time()
        await time.sleep(1.0 - ((time.time() - start_time) % 1.0))
        return True

    def process_transaction(self, data: bytes=None):
        """
        Processes a transaction from witness. This first feeds it through the interpreter, and if
        no errors are thrown, then adds the transaction to the queue.
        :param data: The raw transaction data, assumed to be in byte format
        """
        d, tx = None, None

        try:
            d = self.serializer.serialize(data)
            TestNetTransaction.validate_tx_fields(d)
            tx = TestNetTransaction.from_dict(d)
            self.interpreter.interpret_transaction(tx)
        except Exception as e:
            print("Error in delegate process transaction: {}".format(e))
            return {'error_status': 'Delegate error processing transaction: {}'.format(e)}

        self.queue.enqueue_transaction(tx.payload['payload'])

        if self.queue.queue_size() > MAX_QUEUE_SIZE:
            print('queue exceeded max size...delegate performing consensus')
            self.perform_consensus()

    async def perform_consensus(self):
        """This function holds the key steps to ensure delegate consensus is achieved according to logic above"""

        #  Step one build block by emptying queue
        try:
            block = await self.queue.empty_queue() # node should still receive new tx as it forms a block
        except Exception as e:
            print("Error in forming block: {}".format(e))
            return {'error_status': 'Error in forming block: {}'.format(e)}

        # Step two hash the block byte object to generate unique hash
        try:
            blockhash = await self.hasher.find(self.blockserializer.serialize(block))[1]
        except Exception as e:
            print("Error in hashing block: {}".format(e))
            return {'error_status': 'Error in hashing block: {}'.format(e)}

        # Step three request response hashed message
        self.harmony()

    async def harmony(self):
        try:
            self.dealer_socket.connect(self.dealer_url)
            self.router_socket.bind(self.router_url)
        except Exception as e:
            print("Error in connecting: {}".format(e))
            return {'error_status': 'Error in connecting: {}'.format(e)}

        # read messages from our ROUTER socket to know where they came from
        # write messages to peer DEALER socket