from cilantro.messages.consensus.sub_block_contender import SubBlockContender
from cilantro.messages.consensus.merkle_signature import MerkleSignature, build_test_merkle_sig
from cilantro.messages.transaction.data import TransactionDataBuilder
from cilantro.constants.testnet import TESTNET_MASTERNODES, TESTNET_DELEGATES
from unittest import TestCase
import unittest
from unittest.mock import patch

TEST_SK = TESTNET_MASTERNODES[0]['sk']
TEST_VK = TESTNET_MASTERNODES[0]['vk']
DEL_SK = TESTNET_DELEGATES[0]['sk']
DEL_VK = TESTNET_DELEGATES[0]['vk']

class TestSubBlockContender(TestCase):

    def test_create(self):
        result_hash = b'A' * 64
        input_hash = b'B' * 64
        merkle_leaves = [b'C' * 64] * 5
        signature1 = build_test_merkle_sig(msg=result_hash, sk=DEL_SK, vk=DEL_VK)
        txs1 = [TransactionDataBuilder.create_random_tx(sk=DEL_SK) for i in range(5)]
        sbc1 = SubBlockContender.create(result_hash, input_hash, merkle_leaves, signature1, txs1, 0)
        signature2 = build_test_merkle_sig(msg=result_hash, sk=DEL_SK, vk=DEL_VK)
        txs2 = [TransactionDataBuilder.create_random_tx(sk=DEL_SK) for i in range(5)]
        sbc2 = SubBlockContender.create(result_hash, input_hash, merkle_leaves, signature2, txs2, 1)
        self.assertEqual(sbc1, sbc2)

    def test_serialize_deserialize(self):
        result_hash = b'A' * 64
        input_hash = b'B' * 64
        merkle_leaves = [b'C' * 64] * 5
        signature = build_test_merkle_sig(msg=result_hash, sk=DEL_SK, vk=DEL_VK)
        txs = [TransactionDataBuilder.create_random_tx(sk=DEL_SK) for i in range(5)]
        sbc = SubBlockContender.create(result_hash, input_hash, merkle_leaves, signature, txs, 0)
        clone = SubBlockContender.from_bytes(sbc.serialize())

        self.assertEqual(clone, sbc)

if __name__ == '__main__':
    unittest.main()
