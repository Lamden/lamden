from cilantro.nodes import Node, Subprocess, BIND, CONNECT
import sys
from cilantro.logger.base import get_logger
from cilantro.models import StandardTransaction
from cilantro import Constants
import zmq
import asyncio

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

from threading import Thread


class Router(Thread):
    def __init__(self, callbacks):
        super().__init__()
        self.callbacks = callbacks
        self.daemon = True

    async def listen(self):
        loop = asyncio.get_event_loop()
        tasks = [loop.run_in_executor(None, self.receive, c[0], c[1]) for c in self.callbacks]
        await asyncio.wait(tasks)

    @staticmethod
    def receive(socket, callback):
        while True:
            callback(socket.recv())

class Delegate:
    def __init__(self):
        self.subscriber = Subscriber()
        self.consensus_process = ConsensusProcess()

        callbacks = [(self.subscriber.parent_pipe, self.foo),
                     (self.consensus_process.parent_pipe, self.foo)]

        self.router = Router(callbacks)

        self.router.start()

    def foo(self, msg):
        print(msg)

class Subscriber(Subprocess):
    def __init__(self,
                 name='subscriber',
                 connection_type=BIND,
                 socket_type=zmq.SUB,
                 url=None):
        super().__init__(self, name, connection_type, socket_type, url)

    def zmq_callback(self, msg):
        self.logger.info('Delegate got a message: {}'.format(msg))
        try:
            tx = StandardTransaction.from_bytes(msg)
            self.logger.info('The delegate says: ', tx._data)
        except:
            self.logger.info('Could not deserialize message: {}'.format(msg))


class ConsensusProcess(Subprocess):
    def __init__(self,
                 name='consensus',
                 connection_type=BIND,
                 socket_type=zmq.REP,
                 url=None,
                 signing_key=None,
                 delegates=None):

        super().__init__(self, name, connection_type, socket_type, url)
        self.merkle = None
        self.signing_key = signing_key
        self.delegates = delegates
        self.signatures = []

    def set_merkle(self, merkle):
        self.input.send(merkle)

    def trigger_consensus(self):
        self.input.send(b'')

    def get_signatures(self):
        if self.output.poll():
            return self.output.recv()
        else:
            return None

    def zmq_callback(self, msg):
        self.socket.send(self.merkle)

    def pipe_callback(self, msg):
        '''
        switch statement between merkle tree message and trigger message
        '''
        if len(msg) == 0:
            loop = asyncio.get_event_loop()
            context = zmq.Context()

            async def get_message(future, connection, delegate_verifying_key):
                request_socket = context.socket(socket_type=zmq.REQ)
                request_socket.connect(connection)
                request_socket.send(b'')

                signature = await request_socket.recv()
                future.set_result((signature, delegate_verifying_key))

                request_socket.disconnect(connection)

            def verify_signature(future):
                signature, verifying_key = future.result()
                if ED25519Wallet.verify(verifying_key, self.merkle, signature):
                    self.signatures.append(future.result())

            futures = [asyncio.Future() for _ in range(len(self.delegates))]

            [f.add_done_callback(verify_signature) for f in futures]

            tasks = [get_message(*a) for a in zip(futures, self.delegates)]

            loop.run_until_complete(asyncio.wait(tasks))
            loop.close()

            self.child_output.send(self.signatures)
        else:
            self.merkle = msg