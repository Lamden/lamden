from cilantro_ee.protocol.wallet import Wallet
from cilantro_ee.protocol.transaction import TransactionBuilder
from cilantro_ee.messages import capnp as schemas
import os
import capnp
import secrets
from cilantro_ee.protocol.structures.merkle_tree import MerkleTree
import random
import json


blockdata_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/blockdata.capnp')
subblock_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/subblock.capnp')
transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')
signal_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/signals.capnp')


def random_packed_tx(nonce=0):
    w = Wallet()
    tx = TransactionBuilder(w.verifying_key(), contract=secrets.token_hex(8),
                            function=secrets.token_hex(8),
                            kwargs={secrets.token_hex(8): secrets.token_hex(8)},
                            stamps=random.randint(100_000, 1_000_000),
                            processor=secrets.token_bytes(32),
                            nonce=nonce)

    tx.sign(w.signing_key())

    tx.proof = b'\x00'
    tx.proof_generated = True

    packed_tx = transaction_capnp.Transaction.from_bytes_packed(tx.serialize())
    return packed_tx


def random_tx_data(tx:transaction_capnp.Transaction):
    get_set = {secrets.token_hex(8): secrets.token_hex(8)}

    # Put this hashmap as the state of the contract execution and contruct it into a capnp struct
    tx_data = transaction_capnp.TransactionData.new_message(
        transaction=tx,
        status='SUCC',
        state=json.dumps(get_set),
        contractType=0,
        stampsUsed=random.randint(100_000, 1_000_000)
    )
    return tx_data


def subblock_from_txs(txs, idx=0):
    # Build a subblock. One will do
    tree = MerkleTree.from_raw_transactions([tx.to_bytes_packed() for tx in txs])

    w = Wallet()

    sig = w.sign(tree.root)

    sb = subblock_capnp.SubBlock.new_message(
        merkleRoot=tree.root,
        signatures=[sig],
        merkleLeaves=tree.leaves,
        subBlockIdx=0,
        inputHash=secrets.token_bytes(32),
        transactions=[tx for tx in txs]
    )

    return sb


def random_block(txs=20, subblocks=2, i=1) -> blockdata_capnp.BlockData:
    transactions = []
    for i in range(txs):
        packed_tx = random_packed_tx(nonce=i)
        tx_data = random_tx_data(packed_tx)
        transactions.append(tx_data)

    sbs = [transactions[i::subblocks] for i in range(subblocks)]
    sbs_capnp = [subblock_from_txs(sbs[i], i) for i in range(len(sbs))]

    block = blockdata_capnp.BlockData.new_message(
        blockHash=secrets.token_bytes(32),
        blockNum=i,
        blockOwners=[secrets.token_bytes(32)],
        prevBlockHash=secrets.token_bytes(32),
        subBlocks=[sb for sb in sbs_capnp]
    )

    return block
