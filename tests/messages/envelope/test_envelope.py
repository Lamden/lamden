from cilantro import Constants
from unittest import TestCase
from cilantro.messages import Envelope, MessageMeta, Seal, MessageBase, StandardTransactionBuilder
from cilantro.protocol.structures import EnvelopeAuth

W = Constants.Protocol.Wallets

# TODO createfrommessage

class TestEnvelope(TestCase):

    def _default_meta(self):
        """
        Helper method to build message_meta
        :return: a MessageMeta instance
        """
        t = MessageBase.registry[type(self._default_msg())]
        timestamp = 'now'
        uuid = 1260

        mm = MessageMeta.create(type=t, timestamp=timestamp, uuid=uuid)
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

    def test_create_from_bad_seal(self):
        """
        Test envelope creation with bad seal
        """
        seal = 'hi im a bad seal'
        meta = self._default_meta()
        message = self._default_msg()

        self.assertRaises(Exception, Envelope.create_from_objects, seal, meta, message.serialize())

    def test_create_from_bad_meta(self):
        """
        Test envelope creation with bad seal
        """
        seal = self._default_seal()
        meta = 'hi im a bad message meta'
        message = self._default_msg()

        self.assertRaises(Exception, Envelope.create_from_objects, seal, meta, message.serialize())

    def test_create_from_bad_message(self):
        """
        Test envelope creation with bad seal
        """
        seal = self._default_seal()
        meta = self._default_meta()
        message = 'hi this is a string message with no redeeming qualities'

        self.assertRaises(Exception, Envelope.create_from_objects, seal, meta, message)  # this is not throwing error?

        # TODO fix

    def test_create_from_message(self):
        """
        Tests create_from_message with valid args (no vk passed) creates an envelope valid signature and expected fields
        """
        sk, vk = W.new()
        msg = self._default_msg()
        sender = 'dat boi'

        env = Envelope.create_from_message(message=msg, signing_key=sk)

        self.assertTrue(env.verify_seal())
        self.assertEqual(env.message, msg)
        self.assertEqual(env.seal.verifying_key, vk)

    # TODO: test create_from_message with invalid args

    def test_create_from_message_bad_msg(self):
        """
        Tests create_from_message with invalid message
        """
        sk, vk = W.new()
        msg = 'hi im a bad message'
        sender = 'dat boi'

        self.assertRaises(Exception, Envelope.create_from_message, msg, sk, vk)

    def test_create_from_message_bad_sk(self):
        """
        Tests create_from_message with invalid sk
        """
        sk = 'A' * 127
        msg = 'hi im a bad message'
        sender = 'dat boi'

        self.assertRaises(Exception, Envelope.create_from_message, msg, sk, sender)

    def test_create_from_message_bad_keypair(self):
        """
        test create_from_message passing in sk does and incorrect vk
        """
        sk, vk = W.new()
        sk1, vk1 = W.new()
        msg = self._default_msg()
        sender = 'dat boi'

        env = Envelope.create_from_message(message=msg, signing_key=sk, verifying_key=vk)  # no error

        self.assertEqual(env.seal.verifying_key, vk)

        self.assertRaises(Exception, Envelope.create_from_message, msg, sk, sender, vk1)

        self.assertNotEqual(env.seal.verifying_key, vk1)

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

    def test_validate_envelope(self):
        """
        Tests validate envelope function
        """
        meta = self._default_meta()
        message = self._default_msg()
        sk, vk = W.new()

        signature = EnvelopeAuth.seal(signing_key=sk, meta=meta, message=message)
        seal = Seal.create(signature=signature, verifying_key=vk)

        env = Envelope.create_from_objects(seal=seal, meta=meta, message=message.serialize())

        print('\n\n', env._data, '\n\n', type(env._data))

        env.validate()

    def test_validate_bad_seal(self):
        pass

    def test_validate_bad_metadata(self):
        pass

    def test_validate_bad_message(self):
        pass





