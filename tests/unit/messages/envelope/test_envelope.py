from cilantro_ee.utils.test.testnet_config import set_testnet_config
set_testnet_config('2-2-2.json')

from unittest import TestCase
from unittest.mock import MagicMock

from cilantro_ee.messages.envelope.envelope import Envelope, MessageMeta, Seal
from cilantro_ee.messages.base.base import MessageBase
from cilantro_ee.messages.transaction.contract import ContractTransactionBuilder
from cilantro_ee.nodes.base import NodeTypes

from cilantro_ee.protocol.structures.envelope_auth import EnvelopeAuth
from cilantro_ee.protocol import wallet

from cilantro_ee.constants.testnet import *


class TestEnvelopefromObjects(TestCase):
    """Envelope unit tests using Envelope.create_from_objects() directly to create envelopes"""


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
        message = ContractTransactionBuilder.random_currency_tx()
        return message

    def test_lazy_serialize(self):
        """
        Tests that creating an envelope from_bytes does not try to repack the underlying struct when serialize is called.
        This is b/c the serialize() func should be 'cached' with the binary data passed into from_bytes
        """
        sk, vk = wallet.new()
        message = self._default_msg()

        env = Envelope.create_from_message(message=message, signing_key=sk, verifying_key=vk)
        env_binary = env.serialize()

        clone = Envelope.from_bytes(env_binary)

        clone._data = MagicMock()

        clone_binary = clone.serialize()  # this should not pack the capnp struct (_data) again

        # The Envelope Kitchen Sink lol -- make sure no serialization related API is called
        clone._data.as_builder.assert_not_called()
        clone._data.to_bytes_packed.assert_not_called()
        clone._data.to_bytes.assert_not_called()

    def test_create_from_objects(self):
        """
        Test that create returns an object with expected properties
        """
        seal = self._default_seal()
        meta = self._default_meta()
        message = self._default_msg()

        env = Envelope._create_from_objects(seal=seal, meta=meta, message=message.serialize())

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

        self.assertRaises(Exception, Envelope._create_from_objects, seal, meta, message.serialize())

    def test_create_from_bad_meta(self):
        """
        Test envelope creation with bad meta
        """
        seal = self._default_seal()
        meta = 'hi im a bad message meta'
        message = self._default_msg()

        self.assertRaises(Exception, Envelope._create_from_objects, seal, meta, message.serialize())

    def test_create_from_bad_message(self):
        """
        Test envelope creation with bad message (not bytes)
        """
        seal = self._default_seal()
        meta = self._default_meta()
        message = 'hi this is a string message with no redeeming qualities'

        self.assertRaises(Exception, Envelope._create_from_objects, seal, meta, message)

    def test_verify_seal_invalid(self):
        """
        Tests verifying a seal with an invalid signature
        """
        meta = self._default_meta()
        message = self._default_msg()
        sk, vk = wallet.new()
        sk_prime = 'A' * 64

        signature = EnvelopeAuth.seal(signing_key=sk_prime, meta=meta, message=message)
        seal = Seal.create(signature=signature, verifying_key=vk)

        env = Envelope._create_from_objects(seal=seal, meta=meta, message=message.serialize())

        env.verify_seal()

    def test_validate_envelope(self):
        """
        Tests validate envelope function
        """
        meta = self._default_meta()
        message = self._default_msg()
        sk, vk = wallet.new()

        signature = EnvelopeAuth.seal(signing_key=sk, meta=meta, message=message)
        seal = Seal.create(signature=signature, verifying_key=vk)

        env = Envelope._create_from_objects(seal=seal, meta=meta, message=message.serialize())

        env.validate()

    def test_validate_bad_seal(self):
        meta = self._default_meta()
        message = self._default_msg()
        sk, vk = wallet.new()
        sk2, vk2 = wallet.new()

        signature = EnvelopeAuth.seal(signing_key=sk, meta=meta, message=message)

        seal = Seal.create(signature=signature, verifying_key=vk2)

        env = Envelope._create_from_objects(seal=seal, meta=meta, message=message.serialize())

        self.assertFalse(env.verify_seal())

    def test_validate_bad_metadata(self):
        meta = b'lol'
        message = self._default_msg()
        sk, vk = wallet.new()
        sk2, vk2 = wallet.new()

        signature = EnvelopeAuth.seal(signing_key=sk, meta=meta, message=message)

        seal = Seal.create(signature=signature, verifying_key=vk2)

        self.assertRaises(Exception, Envelope._create_from_objects, seal, meta, message.serialize())

    def test_validate_bad_message(self):
        meta = self._default_meta()
        message = 'lol'
        sk, vk = wallet.new()

        self.assertRaises(Exception, EnvelopeAuth.seal, sk, meta, message)  # auth fails b/c message is not string

    def test_is_from_group_with_one_group(self):
        meta = self._default_meta()
        message = self._default_msg()
        sk, vk = TESTNET_MASTERNODES[0]['sk'], TESTNET_MASTERNODES[0]['vk']

        signature = EnvelopeAuth.seal(signing_key=sk, meta=meta, message=message)
        seal = Seal.create(signature=signature, verifying_key=vk)
        env = Envelope._create_from_objects(seal=seal, meta=meta, message=message.serialize())

        self.assertTrue(env.is_from_group(NodeTypes.MN))

    def test_is_from_group_with_two_group(self):
        meta = self._default_meta()
        message = self._default_msg()
        sk, vk = TESTNET_WITNESSES[0]['sk'], TESTNET_WITNESSES[0]['vk']

        signature = EnvelopeAuth.seal(signing_key=sk, meta=meta, message=message)
        seal = Seal.create(signature=signature, verifying_key=vk)
        env = Envelope._create_from_objects(seal=seal, meta=meta, message=message.serialize())

        self.assertTrue(env.is_from_group([NodeTypes.MN, NodeTypes.WITNESS]))

    def test_is_from_no_groups(self):
        meta = self._default_meta()
        message = self._default_msg()
        sk, vk = TESTNET_DELEGATES[0]['sk'], TESTNET_DELEGATES[0]['vk']

        signature = EnvelopeAuth.seal(signing_key=sk, meta=meta, message=message)
        seal = Seal.create(signature=signature, verifying_key=vk)
        env = Envelope._create_from_objects(seal=seal, meta=meta, message=message.serialize())

        self.assertFalse(env.is_from_group([NodeTypes.MN, NodeTypes.WITNESS]))


class TestEnvelopeFromMessage(TestCase):
    """Envelope tests using Envelope.create_from_message() to create envelopes (the intended way)"""
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
        message = ContractTransactionBuilder.random_currency_tx()
        return message

    def test_create_from_message(self):
        """
        Tests create_from_message with valid args (no vk passed) creates an envelope valid signature and expected fields
        """
        sk, vk = wallet.new()
        msg = self._default_msg()

        env = Envelope.create_from_message(message=msg, signing_key=sk)

        self.assertTrue(env.verify_seal())
        self.assertEqual(env.message, msg)
        self.assertEqual(env.seal.verifying_key, vk)

    def test_create_from_message_bad_msg(self):
        """
        Tests create_from_message with invalid message
        """
        sk, vk = wallet.new()
        msg = 'hi im a bad message'

        self.assertRaises(Exception, Envelope.create_from_message, msg, sk, vk)

    def test_create_from_message_bad_sk(self):
        """
        Tests create_from_message with invalid sk
        """
        sk = 'A' * 127
        msg = self._default_msg()

        self.assertRaises(Exception, Envelope.create_from_message, msg, sk)

    def test_create_from_message_bad_keypair(self):
        """
        test create_from_message passing in sk does and incorrect vk
        """
        sk, vk = wallet.new()
        sk1, vk1 = wallet.new()
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
        sk, vk = wallet.new()
        message = self._default_msg()

        env = Envelope.create_from_message(message=message, signing_key=sk, verifying_key=vk)

        self.assertEqual(env, Envelope.from_bytes(env.serialize()))

    def test_verify_seal(self):
        """
        Tests verify seal with a valid signature
        """
        meta = self._default_meta()
        message = self._default_msg()
        sk, vk = wallet.new()

        signature = EnvelopeAuth.seal(signing_key=sk, meta=meta, message=message)
        seal = Seal.create(signature=signature, verifying_key=vk)

        env = Envelope.create_from_message(message=message, signing_key=sk, verifying_key=vk)

        self.assertTrue(env.verify_seal())
