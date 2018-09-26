from cilantro.messages.block_data.block_metadata import BlockMetaDataRequest, BlockMetaDataReply, OldBlockMetaData
from cilantro.storage.blocks import BlockStorageDriver
from cilantro.utils.test.block_metas import build_valid_block_data
from unittest import TestCase
import unittest

class TestBlockMetaDataRequest(TestCase):

    def test_create(self):
        b_hash = 'A' * 64
        req = BlockMetaDataRequest.create(current_block_hash=b_hash)

        self.assertEqual(req.current_block_hash, b_hash)

    def test_serialize_deserialize(self):
        req = BlockMetaDataRequest.create(current_block_hash='A' * 64)
        clone = BlockMetaDataRequest.from_bytes(req.serialize())

        self.assertEqual(clone, req)

    def test_create_with_bad_hash(self):
        bad_hash = 'lol this is fersure not a valid 64 hex char hash'
        self.assertRaises(Exception, BlockMetaDataRequest.create, bad_hash)


class TestBlockMetaDataReply(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.block_metas = []
        for i in range(5):
            block_data = build_valid_block_data()
            hash = BlockStorageDriver.compute_block_hash(block_data)
            bmd = OldBlockMetaData.create(
                hash=hash,
                merkle_root=block_data['merkle_root'],
                merkle_leaves=block_data['merkle_leaves'],
                prev_block_hash=block_data['prev_block_hash'],
                timestamp=block_data['timestamp'],
                masternode_signature=block_data['masternode_signature'],
                masternode_vk=block_data['masternode_vk'],
                block_contender=block_data['block_contender']
            )
            cls.block_metas.append(bmd)

    def _bad_block(self):
        block_data = build_valid_block_data()
        hash = BlockStorageDriver.compute_block_hash(block_data)
        bmd = OldBlockMetaData.create(
            hash=hash,
            merkle_root=block_data['merkle_root'],
            merkle_leaves=block_data['merkle_leaves'],
            prev_block_hash=block_data['prev_block_hash'],
            timestamp=block_data['timestamp'],
            masternode_signature=block_data['masternode_signature'],
            masternode_vk=block_data['masternode_vk'],
            block_contender=block_data['block_contender']
        )
        return bmd

    def test_create_fails_with_invalid_blockmetas(self):
        """
        Tests that an assertion is raised if BlockMetaDataReply.create(...) is called with a list that contains a
        non OldBlockMetaData instance
        """
        with self.assertRaises(Exception) as e:
            reply = BlockMetaDataReply.create(block_metas=[b'ack'])

    def test_create_with_no_blocks(self):
        reply = BlockMetaDataReply.create(block_metas=[])
        self.assertFalse(reply.block_metas)

    def test_create_with_block_metas_none(self):
        reply = BlockMetaDataReply.create(block_metas=None)
        self.assertFalse(reply.block_metas)

    def test_create_with_blocks(self):
        reply = BlockMetaDataReply.create(block_metas=self.block_metas)
        for expected, actual in zip(reply.block_metas, self.block_metas):
            self.assertEqual(expected, actual)

    def test_create_with_invalid_blocks(self):
        self.block_metas.append(self._bad_block())
        reply = BlockMetaDataReply.create(block_metas=self.block_metas)
        for expected, actual in zip(reply.block_metas, self.block_metas):
            self.assertEqual(expected, actual)

    def test_serialize_deserialize(self):
        reply = BlockMetaDataReply.create(block_metas=self.block_metas)
        clone = BlockMetaDataReply.from_bytes(reply.serialize())
        self.assertEqual(clone, reply)


class TestBlockMetaData(TestCase):
    def _wrap_create():
        def _create(fn, *args, **kwargs):
            def test_fn(self):
                block_data = build_valid_block_data()
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
        bmd = OldBlockMetaData.create(
            hash=hash,
            merkle_root=block_data['merkle_root'],
            merkle_leaves=block_data['merkle_leaves'],
            prev_block_hash=block_data['prev_block_hash'],
            timestamp=block_data['timestamp'],
            masternode_signature=block_data['masternode_signature'],
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
        return OldBlockMetaData.create(
            hash=b'16246',
            merkle_root=block_data['merkle_root'],
            merkle_leaves=block_data['merkle_leaves'],
            prev_block_hash=block_data['prev_block_hash'],
            timestamp=block_data['timestamp'],
            masternode_signature=block_data['masternode_signature'],
            masternode_vk=block_data['masternode_vk'],
            block_contender=block_data['block_contender']
        )

    @_wrap_create()
    @_wrap_assert_fail()
    def test_validate_prevBlockHash_fail(self, block_data, hash):
        return OldBlockMetaData.create(
            hash=hash,
            merkle_root=block_data['merkle_root'],
            merkle_leaves=block_data['merkle_leaves'],
            prev_block_hash=b'346345',
            timestamp=block_data['timestamp'],
            masternode_signature=block_data['masternode_signature'],
            masternode_vk=block_data['masternode_vk'],
            block_contender=block_data['block_contender']
        )

    @_wrap_create()
    @_wrap_assert_fail()
    def test_validate_merkleRoot_fail(self, block_data, hash):
        return OldBlockMetaData.create(
            hash=hash,
            merkle_root=b'5642353',
            merkle_leaves=block_data['merkle_leaves'],
            prev_block_hash=block_data['prev_block_hash'],
            timestamp=block_data['timestamp'],
            masternode_signature=block_data['masternode_signature'],
            masternode_vk=block_data['masternode_vk'],
            block_contender=block_data['block_contender']
        )

    @_wrap_create()
    @_wrap_assert_fail()
    def test_validate_merkleLeaves_fail(self, block_data, hash):
        return OldBlockMetaData.create(
            hash=hash,
            merkle_root=block_data['merkle_root'],
            merkle_leaves=b'22222',
            prev_block_hash=block_data['prev_block_hash'],
            timestamp=block_data['timestamp'],
            masternode_signature=block_data['masternode_signature'],
            masternode_vk=block_data['masternode_vk'],
            block_contender=block_data['block_contender']
        )

    @_wrap_create()
    @_wrap_assert_fail()
    def test_validate_masternodeSignature_fail(self, block_data, hash):
        return OldBlockMetaData.create(
            hash=hash,
            merkle_root=block_data['merkle_root'],
            merkle_leaves=block_data['merkle_leaves'],
            prev_block_hash=block_data['prev_block_hash'],
            timestamp=block_data['timestamp'],
            masternode_signature=b'1234',
            masternode_vk=block_data['masternode_vk'],
            block_contender=block_data['block_contender']
        )

    @_wrap_create()
    @_wrap_assert_fail()
    def test_validate_masternodeVk_fail(self, block_data, hash):
        return OldBlockMetaData.create(
            hash=hash,
            merkle_root=block_data['merkle_root'],
            merkle_leaves=block_data['merkle_leaves'],
            prev_block_hash=block_data['prev_block_hash'],
            timestamp=block_data['timestamp'],
            masternode_signature=block_data['masternode_signature'],
            masternode_vk=b'1234',
            block_contender=block_data['block_contender']
        )

    @_wrap_create()
    @_wrap_assert_fail()
    def test_validate_timestamp_fail(self, block_data, hash):
        return OldBlockMetaData.create(
            hash=hash,
            merkle_root=block_data['merkle_root'],
            merkle_leaves=block_data['merkle_leaves'],
            prev_block_hash=block_data['prev_block_hash'],
            timestamp=1234,
            masternode_signature=block_data['masternode_signature'],
            masternode_vk=block_data['masternode_vk'],
            block_contender=block_data['block_contender']
        )

    @_wrap_create()
    def test_validate_block_contender_fail(self, block_data, hash):
        new_block = build_valid_block_data()
        with self.assertRaises(Exception) as e:
            bmd = OldBlockMetaData.create(
                hash=hash,
                merkle_root=block_data['merkle_root'],
                merkle_leaves=block_data['merkle_leaves'],
                prev_block_hash=block_data['prev_block_hash'],
                timestamp=block_data['timestamp'],
                masternode_signature=block_data['masternode_signature'],
                masternode_vk=block_data['masternode_vk'],
                block_contender=new_block['block_contender']
            )

    def test_serialize_deserialize(self):
        block_data = build_valid_block_data()
        hash = BlockStorageDriver.compute_block_hash(block_data)
        req = OldBlockMetaData.create(
            hash=hash,
            merkle_root=block_data['merkle_root'],
            merkle_leaves=block_data['merkle_leaves'],
            prev_block_hash=block_data['prev_block_hash'],
            timestamp=block_data['timestamp'],
            masternode_signature=block_data['masternode_signature'],
            masternode_vk=block_data['masternode_vk'],
            block_contender=block_data['block_contender']
        )
        clone = OldBlockMetaData.from_bytes(req.serialize())

        self.assertEqual(clone, req)

if __name__ == '__main__':
    unittest.main()
