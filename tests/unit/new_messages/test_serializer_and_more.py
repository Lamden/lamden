from unittest import TestCase
# from cilantro_ee.messages.message import Serializer, signal_capnp, envelope_capnp
from cilantro_ee.core.crypto.wallet import Wallet
from cilantro_ee.core.utils.pow import SHA3POWBytes

import capnp

from cilantro_ee.messages import capnp as schemas

transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')


class TestSerializer(TestCase):
    def test_init(self):
        Serializer(capnp_type=signal_capnp.Signal)

    def test_unpack_returns_equal_capnp_struct(self):
        some_signal = signal_capnp.Signal.new_message(messageType=123)
        packed = some_signal.to_bytes_packed()

        message = envelope_capnp.Message.new_message(payload=packed)
        packed_message = message.to_bytes_packed()

        serializer = Serializer(capnp_type=signal_capnp.Signal)

        unpacked_signal = serializer.unpack(packed_message)

        self.assertEqual(some_signal.messageType, unpacked_signal.messageType)

    def test_pack_returns_same_bytes_as_bytes_packed(self):
        some_signal = signal_capnp.Signal.new_message(messageType=123)
        packed = some_signal.to_bytes_packed()

        message = envelope_capnp.Message.new_message(payload=packed)
        packed_message = message.to_bytes_packed()

        serializer = Serializer(capnp_type=signal_capnp.Signal)
        serialized = serializer.pack(packed)

        self.assertEqual(packed_message, serialized)

    def test_unpack_signed_improperly(self):
        w1 = Wallet()
        w2 = Wallet()

        some_signal = signal_capnp.Signal.new_message(messageType=123)
        packed = some_signal.to_bytes_packed()

        message = envelope_capnp.Message.new_message(payload=packed)
        message.verifyingKey = w1.verifying_key()
        message.signature = w2.sign(message.payload)

        packed_message = message.to_bytes_packed()

        serializer = Serializer(capnp_type=signal_capnp.Signal, sign=True)

        unpacked = serializer.unpack(packed_message)

        self.assertIsNone(unpacked)

    def test_unpack_signed_properly(self):
        w1 = Wallet()

        some_signal = signal_capnp.Signal.new_message(messageType=123)
        packed = some_signal.to_bytes_packed()

        message = envelope_capnp.Message.new_message(payload=packed)
        message.verifyingKey = w1.verifying_key()
        message.signature = w1.sign(message.payload)

        packed_message = message.to_bytes_packed()

        serializer = Serializer(capnp_type=signal_capnp.Signal, sign=True)

        unpacked = serializer.unpack(packed_message)

        self.assertEqual(unpacked.messageType, some_signal.messageType)

    def test_unpack_proof_incorrect(self):
        some_signal = signal_capnp.Signal.new_message(messageType=123)
        packed = some_signal.to_bytes_packed()

        message = envelope_capnp.Message.new_message(payload=packed)
        message.proof = b'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'

        packed_message = message.to_bytes_packed()

        serializer = Serializer(capnp_type=signal_capnp.Signal, prove=True)

        unpacked = serializer.unpack(packed_message)

        self.assertIsNone(unpacked)

    def test_unpack_proof_correct(self):
        some_signal = signal_capnp.Signal.new_message(messageType=123)
        packed = some_signal.to_bytes_packed()

        message = envelope_capnp.Message.new_message(payload=packed)
        message.proof = SHA3POWBytes.find(packed)

        packed_message = message.to_bytes_packed()

        serializer = Serializer(capnp_type=signal_capnp.Signal, prove=True)

        unpacked = serializer.unpack(packed_message)

        self.assertEqual(unpacked.messageType, some_signal.messageType)

    def test_pack_signs_properly(self):
        w1 = Wallet()

        some_signal = signal_capnp.Signal.new_message(messageType=123)
        packed = some_signal.to_bytes_packed()

        message = envelope_capnp.Message.new_message(payload=packed)
        message.verifyingKey = w1.verifying_key()
        message.signature = w1.sign(message.payload)

        packed_message = message.to_bytes_packed()

        serializer = Serializer(capnp_type=signal_capnp.Signal, sign=True)

        packed_and_signed = serializer.pack(packed, w1)

        self.assertEqual(packed_message, packed_and_signed)

    def test_pack_signs_returns_none_if_no_wallet_provided(self):
        some_signal = signal_capnp.Signal.new_message(messageType=123)
        packed = some_signal.to_bytes_packed()

        serializer = Serializer(capnp_type=signal_capnp.Signal, sign=True)

        packed_and_signed = serializer.pack(packed)

        self.assertIsNone(packed_and_signed)

    def test_pack_proves_properly(self):
        some_signal = signal_capnp.Signal.new_message(messageType=123)
        packed = some_signal.to_bytes_packed()

        serializer = Serializer(capnp_type=signal_capnp.Signal, prove=True)

        packed_and_proven = serializer.pack(packed)

        message = envelope_capnp.Message.from_bytes_packed(packed_and_proven)

        self.assertTrue(SHA3POWBytes.check(message.payload, message.proof))
