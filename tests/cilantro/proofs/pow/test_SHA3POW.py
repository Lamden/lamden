from unittest import TestCase
from cilantro.proofs.pow import SHA3POW
import secrets
import hashlib

class TestSHA3POW(TestCase):
    def test_find_solution(self):
        o = secrets.token_bytes(16)
        proof, h = SHA3POW.find(o)

        h = hashlib.sha3_256()
        s = bytes.fromhex(str(proof))
        h.update(o + s)

        self.assertTrue(SHA3POW.check(o, proof))
