# from unittest import TestCase
# from cilantro.messages import *
# from cilantro.protocol.structures import MerkleTree
# from cilantro.protocol.wallets import ED25519Wallet
# from cilantro.storage.delegate import DB, DB_NAME
#
# """
# 1) MN Gets a block contender containing a the leaves of the tree, and a list of signed merkle trees
# 2) MN validates signatures on block contender
# 2) MN async sends out BlockData requests for the nodes who signed the merkle tree
# 4) TODO -- Store block
# """
#
#
# BLOCK_SIZE = 64
# NUM_SIGS = 17
#
#
# def _create_test_transaction(count=1):
#     if count == 1:
#         return StandardTransactionBuilder.random_tx()
#     else:
#         txs = [StandardTransactionBuilder.random_tx() for _ in range(count)]
#         return txs
#
#
# def _create_merkle_sig(merkle: MerkleTree):
#     sk, vk = ED25519Wallet.new()
#     mk_hash = merkle.hash_of_nodes()
#     sig = ED25519Wallet.sign(sk, mk_hash)
#
#     return MerkleSignature.create(sig_hex=sig, timestamp='now', sender=vk)
#
#
# class TestMNBlockchainStorage(TestCase):
#
#     # TODO -- implement
#     def test_that_thang(self):
#         # Create block and block contender
#         txs = _create_test_transaction(count=BLOCK_SIZE)
#         txs_bin = [t.serialize() for t in txs]
#         merkle = MerkleTree(leaves=txs_bin)
#
#         signatures = [_create_merkle_sig(merkle) for _ in range(NUM_SIGS)]
#
#         bc = BlockContender.create(signatures=signatures, nodes=merkle.nodes)
#
#         # Now, at this point, we pretend MN has that block contender and we recreate the data as he
#         # would get it from delegates. The block contender has a list of TX's hashes, and he must get all the
#         # corresponding tx's binaries from the delegates
#         tx_hashes = bc.nodes[len(bc.nodes) // 2:]
#
#         # Mapping of tx hash -> tx binary. These tx hashes get requested from delegates until all values in dict are set
#         block_txs = { t: None for t in tx_hashes}
#
#         # IRL this data would be fetched from delegates, but here we just read from the merkle tree we created earlier
#         for t in block_txs:
#             block_txs[t] = merkle.data_for_hash(t)
#
#         # Ok, this is what MN would have.
#         # - A dict of block data, that is a mapping of tx hashes --> tx binaries
#         # - A list of signatures from the block contender
#
#         with DB('{}_{}'.format(DB_NAME, 0)) as storage:
#
#             signature_text = ''
#
#             for i in signatures:
#                 signature_text += i.signature
#                 signature_text += i.sender
#
#             merkle_text = ''.join(m.hex() for m in merkle.nodes)
#
#             root = merkle.root().hex()
#
#             t = storage.tables.blocks
#
#             storage.execute(t.insert({
#                 'root': root,
#                 'tree': merkle_text,
#                 'signatures': signature_text
#             }))
#
#             for k, v in block_txs.items():
#                 t = storage.tables.transactions
#                 storage.execute(t.insert({
#                     'key': k.hex(),
#                     'value': v.hex()
#                 }))
#
#         a, b, c, d = 69, 1337, 1729, 9000
#         self.assertTrue((a ** 2 + b ** 2) * (c ** 2 + d ** 2) == pow(a * c + b * d, 2) + pow(a * d - b * c, 2))
