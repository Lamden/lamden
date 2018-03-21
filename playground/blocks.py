from cilantro.protocol.structures import MerkleTree
import secrets
from pprint import pprint
from cilantro.db.delegate import *
import pickle
import json

GENESIS = 0


class Block:
    def __init__(self, txs, last_block):
        self.merkle_tree = MerkleTree(txs)
        self.last_block = last_block
        self.hash = self.merkle_tree.root()

    def encode(self):
        return pickle.dumps([self.merkle_tree.raw_leaves, self.last_block])

    @classmethod
    def decode(cls, b):
        block = pickle.loads(b)
        return Block(block[0], block[1])

    def __eq__(self, other):
        if self.hash != other.hash:
            return False
        elif self.merkle_tree.nodes != other.merkle_tree.nodes:
            return False
        elif self.last_block != other.last_block:
            return False
        return True


def generate_blocks(n=128):
    last_block = b''
    blocks = []
    for i in range(n):
        new_block = Block([secrets.token_bytes(16) for _ in range(64)], last_block)
        blocks.append(new_block)
        last_block = new_block.hash
    return blocks


blocks = generate_blocks()
lb = blocks[-1]
backend = LevelDBBackend()

[backend.set(b.hash, b'', b.encode()) for b in blocks]

gotten_blocks = [lb]
while lb.last_block != b'':
    gb = backend.get(lb.last_block, b'')
    gotten_block = Block.decode(gb)
    gotten_blocks.append(gotten_block)
    lb = gotten_block

print(set([b.last_block for b in blocks]) == set([b.last_block for b in gotten_blocks]))
print(set([b.hash for b in blocks]) == set([b.hash for b in gotten_blocks]))
print(len(gotten_blocks))
print(len(blocks))