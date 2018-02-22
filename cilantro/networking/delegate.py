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
import hashlib
import json
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

from threading import Thread
import time

class Delegate(BaseNode):

    def __init__(self, host='127.0.0.1', sub_port='8888', serializer=JSONSerializer, hasher=POW, pub_port='7878',
                 mn_url='http://127.0.0.1:8080'):
        BaseNode.__init__(self, host=host, sub_port=sub_port, pub_port=pub_port, serializer=serializer)
        self.mn_get_balance_url = mn_url + "/balance/all"
        self.mn_post_block_url = mn_url + "/add_block"
        self.mn_get_updates_url = mn_url + '/updates'
        self.hasher = hasher
        self.last_flush_time = time.time()
        self.queue = TransactionQueueDriver()
        self.interpreter = BasicInterpreter(initial_state=self.fetch_state())

        print('preblocking')
        self.thread = Thread(target=self.flush_loop)
        self.thread.start()
        print('postblocking')

    def flush_loop(self):
        while True:
            time.sleep(QUEUE_AUTO_FLUSH_TIME)
            self.perform_consensus()
            print('performing consensus')

    def fetch_state(self):
        print("Fetching full balance state from Masternode...")
        r = requests.get(self.mn_get_balance_url)
        print("Done")
        return r.json()

    def fetch_updates(self):
        print("Fetching balance updates from Masternode...")
        r = requests.get(self.mn_get_updates_url)
        print("Done")
        return r.json()


    def process_transaction(self, data: bytes=None):
        """
        Processes a transaction from witness. This first feeds it through the interpreter, and if
        no errors are thrown, then adds the transaction to the queue.
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

        self.queue.enqueue_transaction((*tx.payload['payload'], tx.payload['metadata']['timestamp']))
        if self.queue.queue_size() > MAX_QUEUE_SIZE:
            print('queue exceeded max size, flushing queue')
            self.perform_consensus()
        elif time.time() - self.last_flush_time >= QUEUE_AUTO_FLUSH_TIME:
            print('time since last queue flush exceeded, flushing queue')
            self.perform_consensus()

        return {'success': 'delegate processed transaction: {}'.format(d)}

    async def handle_req(self, data: bytes=None):
        return self.process_transaction(data=data)

    def perform_consensus(self):
        if self.queue.queue_size() <= 0:
            return

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
        if self.post_block(self.serializer.serialize(block)):
            updates = self.fetch_updates()
            if len(updates) == 0:
                print("Delegate could not get latest updates from masternode. Getting full balance...")
                updates = self.fetch_state()
            self.interpreter.update_state(updates)

    def post_block(self, block: bytes):
        print("Delegate posting block to masternode\nBlock binary: {}".format(block))
        r = requests.post(self.mn_post_block_url, data=block)
        if r.status_code == 200:
            print('Delegate successfully posted block to Masternode')
            return True
        else:
            print("Delegate had problem posting block to Masternode (status code={})".format(r.status_code))
            return False

    async def delegate_time(self):
        """Conditions to check that 1 second has passed"""
        start_time = time.time()
        await time.sleep(1.0 - ((time.time() - start_time) % 1.0))
        return True
