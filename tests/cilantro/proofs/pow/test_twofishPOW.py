from unittest import TestCase
from cilantro.proofs.pow import TwofishPOW
import secrets

class TestTwofishPOW(TestCase):
    def test_find_solution(self):
        o = secrets.token_bytes(32)
        proof, h = TwofishPOW.find(o)
        self.assertTrue(TwofishPOW.check(o, proof))

    def test_find_bad_solution(self):
        o = secrets.token_bytes(32)
        self.assertFalse(TwofishPOW.check(o, secrets.token_hex(16)))