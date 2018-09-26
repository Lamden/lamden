from unittest import TestCase
from cilantro.messages.base.base import MessageBase
from cilantro.messages.envelope.message_meta import MessageMeta
from cilantro.messages.transaction.contract import ContractTransaction

class TestMessageMeta(TestCase):

    def _standard_type(self) -> int:
        return MessageBase.registry[ContractTransaction]

    def test_create(self):
        """
        Tests that create(...) returns a MessageMeta object with the expected properties
        """
        type = self._standard_type()
        timestamp = '1337.126'
        sender = 'me'
        uuid = 1260

        mm = MessageMeta.create(type=type, timestamp=timestamp, uuid=uuid)

        self.assertEqual(mm.type, type)
        self.assertEqual(mm.timestamp, float(timestamp))
        self.assertEqual(mm.uuid, uuid)

    def test_create_random_uuid(self):
        """
        Test a random UUID is created if create does not have a uuid in kwargs
        """
        type = self._standard_type()
        timestamp = '1337.1260'

        mm = MessageMeta.create(type=type, timestamp=timestamp)

        self.assertTrue(mm.uuid)

    def test_eq(self):
        """
        Tests __eq__
        """
        type = self._standard_type()
        timestamp = '1337.126'
        uuid = 1260

        mm = MessageMeta.create(type=type, timestamp=timestamp, uuid=uuid)
        mm2 = MessageMeta.create(type=type, timestamp=timestamp, uuid=uuid)

        self.assertEqual(mm, mm2)

    def test_serialization(self):
        """
        Tests that serialize/deserialize are inverse operations
        """
        type = self._standard_type()
        timestamp = '1337.123'
        uuid = 1260

        mm = MessageMeta.create(type=type, timestamp=timestamp, uuid=uuid)
        mm_clone = (MessageMeta.from_bytes(mm.serialize()))

        self.assertEqual(mm, mm_clone)

    def test_invalid_deserialize(self):
        """
        Tests that attempt to load a MessageMeta object from bytes with invalid data raises an error
        """
        bad_data = b'lololol'

        self.assertRaises(Exception, MessageMeta.from_bytes, bad_data)

    # TODO implement validation and write tests for such
