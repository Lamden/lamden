import unittest, cilantro
from unittest import TestCase
from cilantro.protocol.overlay.msg import *

class TestMsg(TestCase):

    def test_compose_msg(self):
        self.assertEqual(
            compose_msg('hello'),
            bytearray(b'cilantro:hello')
            )

    def test_compose_msg_list(self):
        self.assertEqual(
            compose_msg(['hello','world']),
            bytearray(b'cilantro:hello:world')
            )

    def test_decode_msg(self):
        self.assertEqual(
            decode_msg(b'cilantro:hello:world:my:guy'),
            ('hello', ['world', 'my', 'guy'])
            )

    def test_decode_msg_fail(self):
        self.assertIsNone(
            decode_msg(b'kade:hello:world:my:guy')
            )

if __name__ == '__main__':
    unittest.main()
