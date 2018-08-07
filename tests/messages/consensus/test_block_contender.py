from unittest import TestCase
from cilantro.messages.consensus.block_contender import build_test_contender, BlockContender
from cilantro.messages.consensus.merkle_signature import MerkleSignature
from cilantro.protocol.structures import MerkleTree
from cilantro.protocol import wallet
import secrets
import json


TIMESTAMP = 'now'


class BlockContenderTest(TestCase):
    def _create_merkle_sig(self, msg: bytes):
        """
        Helper method to create a MerkleSignature and wallet keys
        :return: A tuple container (MerkleSignature, signing_key, verifying_key)
        """
        assert type(msg) == bytes, "Must pass in bytes"

        sk, vk = wallet.new()
        signature = wallet.sign(sk, msg)
        ms = MerkleSignature.create(sig_hex=signature, timestamp=TIMESTAMP, sender=vk)

        return ms, sk, vk

    def test_bc_creation(self):
        """
        Tests that a created BlockContender has the expected properties
        """
        msg = b'DEADBEEF'
        nodes = ['A' * 64, 'B' * 64]

        sig1, sk1, vk1 = self._create_merkle_sig(msg)
        sig2, sk2, vk2 = self._create_merkle_sig(msg)
        signatures = [sig1, sig2]

        bc = BlockContender.create(signatures, nodes)

        # assert bc.signatures = signature over all signatures
        for i in range(len(signatures)):
            self.assertTrue(bc.signatures[i] == (signatures[i]))

        for i in range(len(nodes)):
            self.assertTrue(bc.merkle_leaves[i] == (nodes[i]))

    def test_bc_creation_from_bytes(self):
        msg = b'DEADBEEF'
        nodes = ['A' * 64, 'B' * 64]

        sig1, sk1, vk1 = self._create_merkle_sig(msg)
        sig2, sk2, vk2 = self._create_merkle_sig(msg)
        signatures = [sig1, sig2]

        bc = BlockContender.create(signatures, nodes)

        clone = BlockContender.from_bytes(bc.serialize())

        # assert bc.signatures = signature over all signatures
        for i in range(len(signatures)):
            self.assertTrue(clone.signatures[i] == (signatures[i]))

        for i in range(len(nodes)):
            self.assertTrue(clone.merkle_leaves[i] == (nodes[i]))

    def test_create_bc_bad_json(self):
        """
        Tests that attempting to create a BlockContender from bad binary throws an assertion
        """
        # creating a BlockContender with bad json throws an error
        bad_json = b'xVVVVVVVV'
        self.assertRaises(Exception, BlockContender.create, bad_json)

    def test_create_bc_missing_fields(self):
        # tests creating a BlockContender with valid json but missing fields throws an error
        bad_dict1 = {'sig': ['sig1', 'sig2', 'sig3'], 'nodes': None}
        self.assertRaises(Exception, BlockContender.from_data, bad_dict1)

        bad_dict2 = {'sig': None, 'nodes': [1, 2, 3]}
        self.assertRaises(Exception, BlockContender.from_data, bad_dict2)

    def test_create_bc_invaild_signatures(self):
        bad_sigs = ['not merkle sig object', 'also not a merkle sig object']
        mock_nodes = [b'this is a node', b'this is another node']

        self.assertRaises(Exception, BlockContender.create, bad_sigs, mock_nodes)

    def test_create_bc_normal_fields(self):
        msg = b'payload'
        nodes = ['A' * 64, 'B' * 64, 'C' * 64, 'D' * 64]

        sig1, sk1, vk1 = self._create_merkle_sig(msg)
        sig2, sk2, vk2 = self._create_merkle_sig(msg)
        sig3, sk3, vk3 = self._create_merkle_sig(msg)
        sig4, sk4, vk4 = self._create_merkle_sig(msg)

        signatures = [sig1, sig2, sig3, sig4]

        BlockContender.create(signatures, nodes)  # should not throw an error

    def test_deserialize_valid_object(self):
        """
        Tests that the same object is recovered when serialized and deserialized
        """
        msg = b'payload'
        nodes = ['A' * 64, 'B' * 64, 'C' * 64, 'D' * 64]

        sig1, sk1, vk1 = self._create_merkle_sig(msg)
        sig2, sk2, vk2 = self._create_merkle_sig(msg)
        sig3, sk3, vk3 = self._create_merkle_sig(msg)
        sig4, sk4, vk4 = self._create_merkle_sig(msg)

        signatures = [sig1, sig2, sig3, sig4]

        bc = BlockContender.create(signatures, nodes)

        bc_ser = bc.serialize()

        clone = BlockContender.from_bytes(bc_ser)

        for i in range(len(signatures)):
            self.assertEqual(bc.signatures[i], clone.signatures[i])

        for i in range(len(nodes)):
            self.assertEqual(bc.merkle_leaves[i], clone.merkle_leaves[i])

    def test_deserialize_invalid_object(self):
        nodes = ['A' * 64, 'B' * 64, 'C' * 64, 'D' * 64]
        bad_json = {'nodes': nodes, 'signatures': [b'lol'.decode('utf-8'), b'sup'.decode('utf-8'),
                                                   b'cats'.decode('utf-8')]}
        bad_bc = json.dumps(bad_json)

        self.assertRaises(TypeError, BlockContender.from_bytes, bad_bc)  # type error

    def test_build_test_contender(self):
        """
        Tests build_test_contender. This is used exclusively unit tests, so we basically just want to make sure it
        doesn't blow up here first.
        """
        bc = build_test_contender()

    def test_validate_signatures(self):
        nodes = [secrets.token_bytes(8) for _ in range(4)]
        tree = MerkleTree.from_raw_transactions(nodes)

        msg = tree.root

        sig1, sk1, vk1 = self._create_merkle_sig(msg)
        sig2, sk2, vk2 = self._create_merkle_sig(msg)
        sig3, sk3, vk3 = self._create_merkle_sig(msg)
        sig4, sk4, vk4 = self._create_merkle_sig(msg)

        signatures = [sig1, sig2, sig3, sig4]

        bc = BlockContender.create(signatures, merkle_leaves=tree.leaves_as_hex)
        is_valid = bc.validate_signatures()

        self.assertTrue(is_valid)

    def test_validate_signatures_invalid(self):
        nodes = [secrets.token_bytes(8) for _ in range(4)]
        tree = MerkleTree.from_raw_transactions(nodes)

        msg = tree.root

        bad_msg = b'lol this is def not a merkle root'

        sig1, sk1, vk1 = self._create_merkle_sig(msg)
        sig2, sk2, vk2 = self._create_merkle_sig(msg)
        sig3, sk3, vk3 = self._create_merkle_sig(msg)
        sig4, sk4, vk4 = self._create_merkle_sig(bad_msg)

        signatures = [sig1, sig2, sig3, sig4]

        bc = BlockContender.create(signatures, merkle_leaves=tree.leaves_as_hex)
        is_valid = bc.validate_signatures()

        self.assertFalse(is_valid)

    def test_eq(self):
        nodes = [secrets.token_bytes(8) for _ in range(4)]
        tree = MerkleTree.from_raw_transactions(nodes)

        msg = tree.root

        sig1, sk1, vk1 = self._create_merkle_sig(msg)
        sig2, sk2, vk2 = self._create_merkle_sig(msg)
        sig3, sk3, vk3 = self._create_merkle_sig(msg)
        sig4, sk4, vk4 = self._create_merkle_sig(msg)

        signatures = [sig1, sig2, sig3, sig4]

        bc1 = BlockContender.create(signatures, merkle_leaves=tree.leaves_as_hex)
        bc2 = BlockContender.create(signatures, merkle_leaves=tree.leaves_as_hex)

        self.assertEquals(bc1, bc2)
