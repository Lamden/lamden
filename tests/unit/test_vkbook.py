from unittest import TestCase
from cilantro_ee.storage.vkbook import VKBook

class TestVKBook(TestCase):
    def test_submit_new_vkbook(self):
        masternodes = ['a', 'b', 'c']
        delegates = ['d', 'e', 'f']
        stamps = False
        nonces = False

        v = VKBook(masternodes, delegates, stamps=stamps, nonces=nonces)

