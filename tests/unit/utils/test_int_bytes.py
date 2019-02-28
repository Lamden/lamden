from unittest import TestCase
from cilantro_ee.utils import int_to_bytes, bytes_to_int
import secrets
import random


MAX_INT = pow(2, 64)


class TestIntByteUtils(TestCase):

    def test_int_to_bytes(self):
        b = int_to_bytes(12351)
        self.assertTrue(type(b) is bytes)

    def test_bytes_to_int(self):
        for byte_size in range(8 + 1):
            i = bytes_to_int(secrets.token_bytes(byte_size))
            self.assertTrue(type(i) is int)

    def test_inverse_operations(self):
        # We loop hella times cuz ya boy is paranoid it may not work for odds/integers in different ranges
        for _ in range(100):
            i = random.randint(0, MAX_INT)
            clone = bytes_to_int(int_to_bytes(i))
            self.assertEqual(i, clone)

