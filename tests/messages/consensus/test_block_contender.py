from unittest import TestCase
from cilantro.messages import MerkleSignature, BlockContender
from cilantro.protocol.wallets import ED25519Wallet
import json


TIMESTAMP = 'now'


class BlockContenderTest(TestCase):

    def _create_merkle_sig(self, msg: bytes):
        """
        Helper method to create a MerkleSignature and wallet keys
        :return: A tuple container (MerkleSignature, signing_key, verifying_key)
        """
        assert type(msg) == bytes, "Must pass in bytes"

        sk, vk = ED25519Wallet.new()
        signature = ED25519Wallet.sign(sk, msg)
        ms = MerkleSignature.create(sig_hex=signature, timestamp=TIMESTAMP, sender=vk)

        return ms, sk, vk

    def test_creation(self):
        """
        Tests that a created BlockContender has the expected properties
        """
        msg = b'DEADBEEF'
        nodes = [1, 2]

        sig1, sk1, vk1 = self._create_merkle_sig(msg)
        sig2, sk2, vk2 = self._create_merkle_sig(msg)
        signatures = [sig1, sig2]

        bc = BlockContender.create(signatures, nodes)

        # assert bc.signatures = signature over all signatures
        for i in range(len(signatures)):
            self.assertTrue(bc.signatures[i].__eq__(signatures[i]))  # __eq__ way to test signatures are equal

        for i in range(len(nodes)):
            self.assertTrue(bc.nodes[i].__eq__(nodes[i]))

    def test_deserialize_invalid(self):
        """
        Tests that attempting to create a BlockContender from bad binary throws an assertion
        """
        # creating a BlockContender with bad json throws an error
        bad_json = b'xVVVVVVVV'
        self.assertRaises(Exception, BlockContender.create, bad_json)

        # tests creating a BlockContender with valid json but missing fields throws an error
        bad_dict1 = {'sig': ['sig1', 'sig2', 'sig3'], 'nodes': None}
        self.assertRaises(Exception, BlockContender.create, bad_dict1)

        bad_dict2 = {'sig': None, 'nodes': [1, 2, 3]}
        self.assertRaises(Exception, BlockContender.create, bad_dict2)

        msg = b'payload'
        nodes = [1, 2, 3, 4]

        sig1, sk1, vk1 = self._create_merkle_sig(msg)
        sig2, sk2, vk2 = self._create_merkle_sig(msg)
        sig3, sk3, vk3 = self._create_merkle_sig(msg)
        sig4, sk4, vk4 = self._create_merkle_sig(msg)

        signatures = [sig1, sig2, sig3, sig4]

        BlockContender.create(signatures, nodes)  # should not throw an error

    def test_deserialize(self):
        """
        Tests that the same object is recovered when serialized and deserialized
        """
        msg = b'payload'
        nodes = [1, 2, 3, 4]

        sig1, sk1, vk1 = self._create_merkle_sig(msg)
        sig2, sk2, vk2 = self._create_merkle_sig(msg)
        sig3, sk3, vk3 = self._create_merkle_sig(msg)
        sig4, sk4, vk4 = self._create_merkle_sig(msg)

        signatures = [sig1, sig2, sig3, sig4]

        bc = BlockContender.create(signatures, nodes)

        bc_ser = bc.serialize()

        clone = BlockContender.from_bytes(bc_ser)
        print(clone)

        # TODO fix
        for i in range(len(signatures)):
            self.assertEqual(bc.signatures[i], clone.signatures[i])

        for i in range(len(nodes)):
            self.assertEqual(bc.nodes[i], clone.nodes[i])

    # TODO test invalid deserialize with a list of 'bad' signatures, ie sigs that are not valid MerkleSignature binaries
    # manually create the json binary to deserialize an object, by creating a dict with 'nodes' as a list of whatever
    # and 'signatures', which is a list of bad binary strings, ie [b'lol', b'sup', b'cats'], and then json.dumps that
    # thing. Assure an error is rasied when you try to BlockContender.from_bytes(...) on that bad json binary