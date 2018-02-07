from unittest import TestCase
from cilantro.proofs.pow import SHA3POW
import secrets

class TestSHA3POW(TestCase):
    def test_find_solution(self):
        o = secrets.token_bytes(16)
        proof, h = SHA3POW.find(o)
        self.assertTrue(SHA3POW.check(o, proof))

    def test_find_bad_solution(self):
        o = secrets.token_bytes(16)
        self.assertFalse(SHA3POW.check(o, secrets.token_hex(2)))