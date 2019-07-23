from unittest import TestCase
from cilantro_ee.messages._new.message import Serializer, signal_capnp, envelope_capnp
from cilantro_ee.protocol.wallet import Wallet

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