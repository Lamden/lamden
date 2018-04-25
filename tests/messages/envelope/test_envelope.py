from cilantro import Constants
from unittest import TestCase
from cilantro.messages import Envelope, MessageMeta, Seal, MessageBase, StandardTransactionBuilder
from cilantro.protocol.structures import EnvelopeAuth

W = Constants.Protocol.Wallets


class TestEnvelope(TestCase):

    def _default_meta(self):
        """
        Helper method to build message_meta
        :return: a MessageMeta instance
        """
        t = MessageBase.registry[type(self._default_msg())]
        timestamp = 'now'
        sender = 'me'
        uuid = 1260

        mm = MessageMeta.create(type=t, sender=sender, timestamp=timestamp, uuid=uuid)
        return mm

    def _default_seal(self):
        """
        Helper method to build a Seal
        :return: a Seal instance
        """
        sig = 'A' * 128
        vk = 'A' * 68
        return Seal.create(signature=sig, verifying_key=vk)

    def _default_msg(self):
        # TODO -- write default TestMessage class
        # We should really have a default TestMessage object that is a bare-minimum subclass of MessageBase
        # instead of using other live objects for these kinds of tests
        message = StandardTransactionBuilder.random_tx()
        return message

    def test_create_from_objects(self):
        """
        Test that create returns an object with expected properties
        """
        seal = self._default_seal()
        meta = self._default_meta()
        message = self._default_msg()

        env = Envelope.create_from_objects(seal=seal, meta=meta, message=message.serialize())

        self.assertEqual(env.seal, seal)
        self.assertEqual(env.meta, meta)
        self.assertEqual(env.message, message)

    # TODO: test create_from_object with invalid objects

    def test_create_from_message(self):
        """
        Tests create_from_message with valid args (no vk passed) creates an envelope valid signature and expected fields
        """
        sk, vk = W.new()
        msg = self._default_msg()
        sender = 'dat boi'

        env = Envelope.create_from_message(message=msg, signing_key=sk, sender_id=sender)

        self.assertTrue(env.verify_seal())
        self.assertEqual(env.message, msg)
        self.assertEqual(env.meta.sender, sender)
        self.assertEqual(env.seal.verifying_key, vk)

    # TODO: test create_from_message with invalid args

    # TODO: test create_from_message passing in sk does and incorrect vk

    def test_serialize_from_objects(self):
        """
        Tests that serialize/deserialize are inverse operations with from_objects factory function
        """
        seal = self._default_seal()
        meta = self._default_meta()
        message = self._default_msg()

        env = Envelope.create_from_objects(seal=seal, meta=meta, message=message.serialize())

        self.assertEqual(env, Envelope.from_bytes(env.serialize()))

    def test_verify_seal(self):
        """
        Tests verify seal with a valid signature
        """
        meta = self._default_meta()
        message = self._default_msg()
        sk, vk = W.new()

        signature = EnvelopeAuth.seal(signing_key=sk, meta=meta, message=message)
        seal = Seal.create(signature=signature, verifying_key=vk)

        env = Envelope.create_from_objects(seal=seal, meta=meta, message=message.serialize())

        self.assertTrue(env.verify_seal())

    def test_verify_seal_invalid(self):
        """
        Tests verifying a seal with an invalid signature
        """
        meta = self._default_meta()
        message = self._default_msg()
        sk, vk = W.new()
        sk_prime = 'A' * 64

        signature = EnvelopeAuth.seal(signing_key=sk_prime, meta=meta, message=message)
        seal = Seal.create(signature=signature, verifying_key=vk)

        env = Envelope.create_from_objects(seal=seal, meta=meta, message=message.serialize())

        self.assertFalse(env.verify_seal())

    # TODO: implement and test validation

    # TODO: test message deserialization





