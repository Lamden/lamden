from cilantro.messages.consensus.block_contender import build_test_contender, BlockContender
from cilantro.messages.transaction.base import build_test_transaction
from cilantro.protocol.wallets import ED25519Wallet
from cilantro.protocol.structures.merkle_tree import MerkleTree
from cilantro import Constants

def build_valid_block_data(num_transactions=4) -> dict:
    """
    Utility method to build a dictionary with all the params needed to invoke store_block
    :param num_transactions:
    :return:
    """
    mn_sk = Constants.Testnet.Masternodes[0]['sk']
    mn_vk = ED25519Wallet.get_vk(mn_sk)
    timestamp = 9000

    raw_transactions = [build_test_transaction().serialize() for _ in range(num_transactions)]

    tree = MerkleTree(raw_transactions)
    merkle_leaves = tree.leaves_as_concat_hex_str
    merkle_root = tree.root_as_hex

    bc = build_test_contender(tree=tree)

    prev_block_hash = '0' * 64

    mn_sig = ED25519Wallet.sign(mn_sk, tree.root)

    return {
        'prev_block_hash': prev_block_hash,
        'block_contender': bc,
        'merkle_leaves': merkle_leaves,
        'merkle_root': merkle_root,
        'masternode_signature': mn_sig,
        'masternode_vk': mn_vk,
        'timestamp': timestamp
    }
