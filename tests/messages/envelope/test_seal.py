from unittest import TestCase
from cilantro.messages import Seal


class TestSeal(TestCase):

    def test_eq(self):
        """
        tests __eq__
        """
        signature = "A" * 128
        vk = "A" * 64

        seal = Seal.create(signature=signature, verifying_key=vk)
        seal2 = Seal.create(signature=signature, verifying_key=vk)

        self.assertEqual(seal, seal2)

    def test_create(self):
        """
        Tests creating a seal produces a Seal object with the expected properties
        """
        signature = "A" * 128
        vk = "A" * 64

        seal = Seal.create(signature=signature, verifying_key=vk)

        self.assertEqual(seal.signature, signature)
        self.assertEqual(seal.verifying_key, vk)

    def test_serialization(self):
        """
        Tests that serialize/deserialize are inverse operations
        """
        signature = "A" * 128
        vk = "A" * 64

        seal = Seal.create(signature=signature, verifying_key=vk)
        seal_clone = Seal.from_bytes(seal.serialize())

        self.assertEqual(seal, seal_clone)

    def test_invalid_deserialize(self):
        """
        Tests that attempt to load a Seal object from bytes with invalid data raises an error
        """
        bad_data = b'some random string that is obviously not a Seal capnp struct binary'
        self.assertRaises(Exception, Seal.from_bytes, bad_data)

    # TODO -- tests for validation of signature and verifying_key (valid hex/len)
