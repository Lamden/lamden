import secrets
from cilantro.models import MerkleTree
from cilantro.protocol.wallets import ED25519Wallet
import hashlib

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

print('\n===MERKLE TREE HASHED===')
h = hashlib.sha3_256()
[h.update(mm) for mm in m.nodes]
print(h.digest().hex())

print('\n===ENTIRE MERKLE TREE===')
[print(mm.hex()) for mm in m.nodes]

print('\n===SIGNATURE OF MERKLE HASH===')
[print(ED25519Wallet.sign(k[0], h.digest())) for k in delegates]