import secrets
from cilantro.messages import MerkleTree
from cilantro.protocol.wallet import Wallet
import hashlib
from cilantro.nodes import Subprocess, BIND, CONNECT

import zmq
import asyncio
from pprint import pprint

'''
    For consensus, the masternode gets the following from the delegates:
    The merkle tree as a list
    The hash of the merkle tree
    The signature list of the hash of the merkle tree

    AKA: m, h(m), s(h(m)) for all delegates
    
    1. test that we can make a merkle tree and sign it pretty quickly (DONE)
    2. test that we can make a merkle tree on a whole bunch of nodes and sign it between each other
'''

# create real transactions and a real merkle tree
true_txs = [secrets.token_bytes(64) for i in range(100)]
m = MerkleTree(true_txs)

# create fake transactions and a fake merkle tree
fake_txs = [secrets.token_bytes(64) for i in range(100)]
n = MerkleTree(fake_txs)

# generate the delegates with new wallets
delegates = [Wallet.new() for i in range(64)]

connection_list = ['inproc://{}'.format(k[1]) for k in delegates]


def print_stuff():
    pprint(connection_list)

    print('\n===MERKLE TREE HASHED===')
    h = hashlib.sha3_256()
    [h.update(mm) for mm in m.merkle_leaves]
    print(h.digest().hex())

    print('\n===ENTIRE MERKLE TREE===')
    [print(mm.hex()) for mm in m.merkle_leaves]

    print('\n===SIGNATURE OF MERKLE HASH===')
    [print(Wallet.sign(k[0], h.digest())) for k in delegates]


signature_list = []


def request_from_all_nodes():
    # asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    loop = asyncio.get_event_loop()

    context = zmq.Context()

    # replace with while signature_list length < 1/2 delegates
    # choose a random connection and request a response
    # verify that the signature is indeed accurate
    # add that signature to a list of signatures
    # stop when all of the signatures have been selected

    delegates_to_request = list(connection_list)

    async def get_message(future, connection):
        request_socket = context.socket(socket_type=zmq.REQ)
        request_socket.connect(connection)
        request_socket.send(b'')

        await asyncio.sleep(1)
        future.set_result(b'yay')

        request_socket.disconnect(connection)

    def verify_signature(future):
        from cilantro.logger import get_logger
        logger = get_logger('threads')
        logger.debug('writing to thread')
        signature_list.append(future.result())

    futures = [asyncio.Future() for _ in range(len(delegates_to_request))]

    [f.add_done_callback(verify_signature) for f in futures]

    tasks = [get_message(*a) for a in zip(futures, delegates_to_request)]

    loop.run_until_complete(asyncio.wait(tasks))
    loop.close()


class ConsensusProcess(Subprocess):
    def __init__(self,
                 name='consensus',
                 connection_type=BIND,
                 socket_type=zmq.REP,
                 url=connection_list[0],
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
                if Wallet.verify(verifying_key, self.merkle, signature):
                    self.signatures.append(future.result())

            futures = [asyncio.Future() for _ in range(len(self.delegates))]

            [f.add_done_callback(verify_signature) for f in futures]

            tasks = [get_message(*a) for a in zip(futures, self.delegates)]

            loop.run_until_complete(asyncio.wait(tasks))
            loop.close()

            self.child_output.send(self.signatures)
        else:
            self.merkle = msg


class Delegate:
    def __init__(self):
        self.consensus_process = ConsensusProcess()
