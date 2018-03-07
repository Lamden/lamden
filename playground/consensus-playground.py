import secrets
from cilantro.models import MerkleTree
from cilantro.protocol.wallets import ED25519Wallet
import hashlib

from multiprocessing import Process
import zmq
from cilantro import Constants
import asyncio
from aioprocessing import AioPipe
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
delegates = [ED25519Wallet.new() for i in range(64)]

connection_list = ['inproc://{}'.format(k[1]) for k in delegates]


def print_stuff():
    pprint(connection_list)

    print('\n===MERKLE TREE HASHED===')
    h = hashlib.sha3_256()
    [h.update(mm) for mm in m.nodes]
    print(h.digest().hex())

    print('\n===ENTIRE MERKLE TREE===')
    [print(mm.hex()) for mm in m.nodes]

    print('\n===SIGNATURE OF MERKLE HASH===')
    [print(ED25519Wallet.sign(k[0], h.digest())) for k in delegates]

signature_list = []

def request_from_all_nodes():
    #asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
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
        signature_list.append(future.result())

    futures = [asyncio.Future() for _ in range(len(delegates_to_request))]

    [f.add_done_callback(verify_signature) for f in futures]

    tasks = [get_message(*a) for a in zip(futures, delegates_to_request)]

    loop.run_until_complete(asyncio.wait(tasks))
    loop.close()

def respond():
    loop = asyncio.get_event_loop()

    context = zmq.Context()

    async def get_message(future, connection):
        response_socket = context.socket(socket_type=zmq.REQ)
        response_socket.bind(connection)
        await response_socket.recv()
        response_socket.send(b'signature')

        future.set_result(b'yay')

        response_socket.disconnect(connection)

