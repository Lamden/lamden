from cilantro.messages import BlockMetaData
from cilantro.protocol.structures.merkle_tree import MerkleTree
from cilantro.messages.consensus.block_contender import build_test_contender, BlockContender
from cilantro.messages.transaction.base import build_test_transaction
from cilantro.protocol.wallets import ED25519Wallet
from cilantro.db import BlockStorageDriver
from cilantro import Constants
from unittest import TestCase
import unittest

class TestBlockMetaData(TestCase):

    def _build_valid_block_data(self, num_transactions=4) -> dict:
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

    def _wrap_create():
        def _create(fn, *args, **kwargs):
            def test_fn(self):
                block_data = self._build_valid_block_data()
                hash = BlockStorageDriver.compute_block_hash(block_data)
                return fn(self, block_data, hash)
            return test_fn
        return _create

    def _wrap_assert_fail():
        def _fail(fn, *args, **kwargs):
            def test_fn(self, *args, **kwargs):
                with self.assertRaises(Exception) as e:
                    bmd = fn(self, *args, **kwargs)
            return test_fn
        return _fail

    @_wrap_create()
    def test_create(self, block_data, hash):
        bmd = BlockMetaData.create(
            hash=hash,
            merkle_root=block_data['merkle_root'],
            merkle_leaves=block_data['merkle_leaves'],
            prev_block_hash=block_data['prev_block_hash'],
            timestamp=block_data['timestamp'],
            masternode_sig=block_data['masternode_signature'],
            masternode_vk=block_data['masternode_vk'],
            block_contender=block_data['block_contender']
        )
        self.assertEqual(block_data['merkle_root'], bmd.merkle_root)
        self.assertEqual(block_data['merkle_leaves'], ''.join(bmd.merkle_leaves))
        self.assertEqual(block_data['prev_block_hash'], bmd.prev_block_hash)
        self.assertEqual(block_data['timestamp'], bmd.timestamp)
        self.assertEqual(block_data['masternode_signature'], bmd.masternode_signature)
        self.assertEqual(block_data['masternode_vk'], bmd.masternode_vk)
        self.assertEqual(block_data['block_contender'], bmd.block_contender)

    @_wrap_create()
    @_wrap_assert_fail()
    def test_validate_hash_fail(self, block_data, hash):
        return BlockMetaData.create(
            hash=b'16246',
            merkle_root=block_data['merkle_root'],
            merkle_leaves=block_data['merkle_leaves'],
            prev_block_hash=block_data['prev_block_hash'],
            timestamp=block_data['timestamp'],
            masternode_sig=block_data['masternode_signature'],
            masternode_vk=block_data['masternode_vk'],
            block_contender=block_data['block_contender']
        )

    @_wrap_create()
    @_wrap_assert_fail()
    def test_validate_prevBlockHash_fail(self, block_data, hash):
        return BlockMetaData.create(
            hash=hash,
            merkle_root=block_data['merkle_root'],
            merkle_leaves=block_data['merkle_leaves'],
            prev_block_hash=b'346345',
            timestamp=block_data['timestamp'],
            masternode_sig=block_data['masternode_signature'],
            masternode_vk=block_data['masternode_vk'],
            block_contender=block_data['block_contender']
        )

    @_wrap_create()
    @_wrap_assert_fail()
    def test_validate_merkleRoot_fail(self, block_data, hash):
        return BlockMetaData.create(
            hash=hash,
            merkle_root=b'5642353',
            merkle_leaves=block_data['merkle_leaves'],
            prev_block_hash=block_data['prev_block_hash'],
            timestamp=block_data['timestamp'],
            masternode_sig=block_data['masternode_signature'],
            masternode_vk=block_data['masternode_vk'],
            block_contender=block_data['block_contender']
        )

    @_wrap_create()
    @_wrap_assert_fail()
    def test_validate_merkleLeaves_fail(self, block_data, hash):
        return BlockMetaData.create(
            hash=hash,
            merkle_root=block_data['merkle_root'],
            merkle_leaves=b'22222',
            prev_block_hash=block_data['prev_block_hash'],
            timestamp=block_data['timestamp'],
            masternode_sig=block_data['masternode_signature'],
            masternode_vk=block_data['masternode_vk'],
            block_contender=block_data['block_contender']
        )

    @_wrap_create()
    @_wrap_assert_fail()
    def test_validate_masternodeSignature_fail(self, block_data, hash):
        return BlockMetaData.create(
            hash=hash,
            merkle_root=block_data['merkle_root'],
            merkle_leaves=block_data['merkle_leaves'],
            prev_block_hash=block_data['prev_block_hash'],
            timestamp=block_data['timestamp'],
            masternode_sig=b'1234',
            masternode_vk=block_data['masternode_vk'],
            block_contender=block_data['block_contender']
        )

    @_wrap_create()
    @_wrap_assert_fail()
    def test_validate_masternodeVk_fail(self, block_data, hash):
        return BlockMetaData.create(
            hash=hash,
            merkle_root=block_data['merkle_root'],
            merkle_leaves=block_data['merkle_leaves'],
            prev_block_hash=block_data['prev_block_hash'],
            timestamp=block_data['timestamp'],
            masternode_sig=block_data['masternode_signature'],
            masternode_vk=b'1234',
            block_contender=block_data['block_contender']
        )

    @_wrap_create()
    @_wrap_assert_fail()
    def test_validate_timestamp_fail(self, block_data, hash):
        return BlockMetaData.create(
            hash=hash,
            merkle_root=block_data['merkle_root'],
            merkle_leaves=block_data['merkle_leaves'],
            prev_block_hash=block_data['prev_block_hash'],
            timestamp=1234,
            masternode_sig=block_data['masternode_signature'],
            masternode_vk=block_data['masternode_vk'],
            block_contender=block_data['block_contender']
        )

    @_wrap_create()
    def test_validate_block_contender_fail(self, block_data, hash):
        new_block = self._build_valid_block_data()
        with self.assertRaises(Exception) as e:
            bmd = BlockMetaData.create(
                hash=hash,
                merkle_root=block_data['merkle_root'],
                merkle_leaves=block_data['merkle_leaves'],
                prev_block_hash=block_data['prev_block_hash'],
                timestamp=block_data['timestamp'],
                masternode_sig=block_data['masternode_signature'],
                masternode_vk=block_data['masternode_vk'],
                block_contender=new_block['block_contender']
            )

    def test_serialize_deserialize(self):
        block_data = self._build_valid_block_data()
        hash = BlockStorageDriver.compute_block_hash(block_data)
        req = BlockMetaData.create(
            hash=hash,
            merkle_root=block_data['merkle_root'],
            merkle_leaves=block_data['merkle_leaves'],
            prev_block_hash=block_data['prev_block_hash'],
            timestamp=block_data['timestamp'],
            masternode_sig=block_data['masternode_signature'],
            masternode_vk=block_data['masternode_vk'],
            block_contender=block_data['block_contender']
        )
        clone = BlockMetaData.from_bytes(req.serialize())

        self.assertEqual(clone, req)

if __name__ == '__main__':
    unittest.main()
