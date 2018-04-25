from unittest import TestCase
from cilantro.messages import MessageMeta


class TestMessageMeta(TestCase):

    def test_create(self):
        """
        Tests that create(...) returns a MessageMeta object with the expected properties
        """
        type = 1
        timestamp = 'now'
        sender = 'me'
        uuid = 1260

        mm = MessageMeta.create(type=type, sender=sender, timestamp=timestamp, uuid=uuid)

        self.assertEqual(mm.type, type)
        self.assertEqual(mm.sender, sender)
        self.assertEqual(mm.timestamp, timestamp)
        self.assertEqual(mm.uuid, uuid)

    def test_create_random_uuid(self):
        """
        Test a random UUID is created if create does not have a uuid in kwargs
        """
        type = 1
        timestamp = 'now'
        sender = 'me'

        mm = MessageMeta.create(type=type, sender=sender, timestamp=timestamp)

        self.assertTrue(mm.uuid)

    def test_eq(self):
        """
        Tests __eq__
        """
        type = 1
        timestamp = 'now'
        sender = 'me'
        uuid = 1260

        mm = MessageMeta.create(type=type, sender=sender, timestamp=timestamp, uuid=uuid)
        mm2 = MessageMeta.create(type=type, sender=sender, timestamp=timestamp, uuid=uuid)

        self.assertEqual(mm, mm2)

    def test_serialization(self):
        """
        Tests that serialize/deserialize are inverse operations
        """
        type = 1
        timestamp = 'now'
        sender = 'me'
        uuid = 1260

        mm = MessageMeta.create(type=type, sender=sender, timestamp=timestamp, uuid=uuid)
        mm_clone = (MessageMeta.from_bytes(mm.serialize()))

        self.assertEqual(mm, mm_clone)

    def test_invalid_deserialize(self):
        """
        Tests that attempt to load a MessageMeta object from bytes with invalid data raises an error
        """
        bad_data = b'lololol'

        self.assertRaises(Exception, MessageMeta.from_bytes, bad_data)

    # TODO implement validation and write tests for such
