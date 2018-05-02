from unittest import TestCase

from cilantro.messages.base import MessageBase

"""
TestMessage bare bones implementation of MessageBase for Testing purposes only
"""


class TestMessage(TestCase):
        def test_create_message(self):
            msg = {'test': 'json'}
            mb = MessageBase(data=msg)
            return mb

