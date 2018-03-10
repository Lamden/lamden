from cilantro.protocol.wallets import ED25519Wallet
from cilantro.nodes import Node, Subprocess, BIND, CONNECT, zmq_listener, zmq_sender, pipe_listener, zmq_two_ways, Router
import sys
from cilantro.logger.base import get_logger
from cilantro.models import StandardTransaction, Poke, MerkleTree
from cilantro import Constants
import zmq
import asyncio
from aioprocessing import AioPipe
from multiprocessing import Process
from cilantro.models import StandardTransaction, Message, MerkleTree, Poke
from cilantro.models.message.message import MODEL_TYPES # TODO -- find a better home for these constants
from cilantro.db.delegate.transaction_queue_driver import TransactionQueueDriver
from cilantro.protocol.interpreters import VanillaInterpreter
# if sys.platform != 'win32':
#     import uvloop
#     asyncio.set_event_loop_policy(uvloop.EventLoopPolicy)

"""
    Delegates

    Delegates are the "miners" of the Cilantro blockchain in that they opportunistically bundle up transaction into 
    blocks and are rewarded with TAU for their actions. They receive approved transaction from delegates and broadcast
    blocks based on a 1 second or 10,000 transaction limit per block. They should be able to connect/drop from the 
    network seamlessly as well as coordinate blocks amongst themselves.
    
     Delegate logic:   
        Step 1) Delegate takes 10k transaction from witness and forms a block
        Step 2) Block propagates across the network to other delegates
        Step 3) Delegates pass around in memory DB hash to confirm they have the same blockchain state
        Step 4) Next block is mined and process repeats

        zmq pattern: subscribers (delegates) need to be able to communicate with one another. this can be achieved via
        a push/pull pattern where all delegates push their state to sink that pulls them in, but this is centralized.
        another option is to use ZMQ stream to have the tcp sockets talk to one another outside zmq
"""

class Delegate:
    def __init__(self, url, port, delegates: list, signing_key):
        self.log = get_logger("Delegate-{}".format(port))
        self.port = port
        self.url = url

        sub_url = 'tcp://127.0.0.1:{}'.format(Constants.Witness.PubPort)
        rep_url = 'tcp://*:{}'.format(port)

        self.log.debug("Spinning up delegate /w sub_url={}, rep_url={}".format(sub_url, rep_url))

        self.delegates = list(filter(lambda d: d['port'] is not port, delegates))
        self.log.debug("delegate list (excluding self): {}".format(self.delegates))
        self.signing_key = signing_key

        # consensus variables
        self.merkle = None
        self.signature = b'too soon bro'
        self.signatures = []

        # NOTE -- might have to deepcopy below
        self.left_in_consensus = list(self.delegates)

        self.subscriber_pipe, self.subscriber_process = zmq_listener(zmq.SUB, CONNECT, sub_url)
        self.subscriber_process.start()

        self.consensus_replier_pipe, self.consensus_replier_process = zmq_two_ways(zmq.REP, BIND, rep_url)
        self.consensus_replier_process.start()

        callbacks = [(self.subscriber_pipe, self.handle_message),
                     (self.consensus_replier_pipe, self.handle_message)]

        self.router = Router(callbacks)

        self.router.start()

        # Queue + Interpreter
        self.queue = TransactionQueueDriver(db=str(self.port)[-1:])
        self.interpreter = VanillaInterpreter(port=str(self.port))

        # Flush queue on boot
        self.log.debug("Delegate flushing queue on boot")
        self.queue.dequeue_all()

    def handle_message(self, msg):
        self.log.debug("Got message: {}".format(msg))

        m = None
        try:
            m = Message.from_bytes(msg)
            self.log.debug("Unpacked msg with data: {}".format(m._data))
        except Exception as e:
            self.log.error("Error deserializing msg: {}".format(e))

        # Route m
        if m.type == MODEL_TYPES[StandardTransaction.name]['id']:
            self.log.debug("Got a standard TX on delegate!!")
            # self.log.debug("about to access m.payload")
            # p = m.payload
            # self.log.debug("done accessing m.payload")
            self.handle_tx(m.payload)
        elif m.type == MODEL_TYPES[MerkleTree.name]['id']:
            self.handle_merkle(m.payload)
        elif m.type == MODEL_TYPES[Poke.name]['id']:
            self.handle_poke()
        else:
            self.log.error("Got message of unknown type: {}".format(m.type))
            raise ValueError("Got message of unknown type: {}".format(m.type))

    def handle_tx(self, tx_binary):
        self.log.debug("Unpacking standard tx")
        tx = None

        # Deserialize tx
        try:
            tx = StandardTransaction.from_bytes(tx_binary)
        except Exception as e:
            self.log.error("Error unpacking standard transaction: {}".format(e))

        # Feed tx to interpreter
        try:
            self.log.debug("Interpretting standard tx")
            self.interpreter.interpret_transaction(tx)
        except Exception as e:
            self.log.error("Error interpretting tx: {}".format(e))

        self.log.debug("Successfully interpretered tx...adding it to queue")
        self.queue.enqueue_transaction(tx.serialize())

        if self.queue.queue_size() >= 4:
            self.gather_consensus()

    def handle_merkle(self, merkle_payload):
        merkle = MerkleTree.from_bytes(merkle_payload)
        self.log.debug("Handle merkle called with data {}".format(merkle))

        vk = Constants.Protocol.Wallets.verifying_key(merkle['vk'])
        sig = merkle['signature']

        if Constants.Protocol.Wallets.verify(vk, self.merkle.hash_of_nodes, sig) and \
                vk not in [x[0] for x in self.signatures] and \
                vk in self.left_in_consensus:

            self.signatures.append((vk, sig))
            i = self.left_in_consensus.index(vk)
            self.left_in_consensus.pop(i)

        if len(self.signatures) > len(self.delegates) // 2:
            data_to_mn = [self.merkle.hash_of_nodes(), self.merkle.nodes, self.signatures]
            self.left_in_consensus = list(self.delegate_keys)
            self.signatures = []
            self.log.info("GOT DAT MASTERNODE DATA: {}".format(data_to_mn))

    def handle_poke(self):
        self.log.debug("Stop poking me")
        # self.consensus_replier_pipe.send(self.signature)
        self.log.debug("I replied to the poke with sig {}".format(self.signature))

    def gather_consensus(self):
        self.log.debug("Starting consesnsus.")

        # Get all tx
        tx = self.queue.dequeue_all()

        # Merkleize them and sign
        self.merkle = MerkleTree(tx)
        self.signature = ED25519Wallet.sign(self.signing_key, self.merkle.hash_of_nodes())
        self.signature = self.signature.encode()

        self.log.debug('signature is {}'.format(self.signature))

        # Time to gather from others
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        context = zmq.Context()

        # TODO -- why is this not getting fired async?
        async def get_message(future, connection):
            request_socket = context.socket(socket_type=zmq.REQ)
            request_socket.connect(connection)

            self.log.debug("Poking url: {}".format(connection))
            
            poke = Poke.create()
            poke_msg = Message.create(Poke, poke.serialize())

            request_socket.send(poke_msg.serialize())
            msg = await request_socket.recv()

            self.log.debug("Got request from the poked delegate: {}".format(msg))

            future.set_result(msg)
            request_socket.disconnect(connection)

        def verify_signature(future):
            self.handle_message(future.result())

        futures = [asyncio.Future() for _ in range(len(self.delegates))]

        [f.add_done_callback(verify_signature) for f in futures]

        tasks = [get_message(*a) for a in zip(futures, ['{}:{}'.format(d['url'], d['port']) for d in self.delegates])]

        self.log.debug("# of poke tasks: {}".format(len(tasks)))

        loop.run_until_complete(asyncio.wait(tasks))
        loop.close()


