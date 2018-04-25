from cilantro import Constants
from cilantro.protocol.structures import EnvelopeAuth
from unittest import TestCase

class TestEnvelopeAuth(TestCase):

    def test_verify(self):
        """
        Tests a verifying a valid signature for metadata and data
        """
        pass