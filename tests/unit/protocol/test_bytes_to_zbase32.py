from unittest import TestCase
from cilantro_ee.core.crypto import zbase


class TestZBase(TestCase):
    def test_bytes_to_zbase_works(self):
        crypt = zbase.bytes_to_zbase32(b'hello123xx')
        self.assertEqual(crypt, 'pb1sa5dxgr3dg6da')

    def test_zbase_to_bytes_works(self):
        decrypt = zbase.zbase32_to_bytes('ctbs63dfrb7n4aubqp114c31')
        self.assertEqual(decrypt, b'dCode z-base-32')
