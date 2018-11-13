from cilantro.messages.base.base_signal import SignalBase
from unittest import TestCase


class TestSignalBase(TestCase):

    def test_serialize_deserialize(self):
        sig = SignalBase.create()
        clone = SignalBase.from_bytes(sig.serialize())
