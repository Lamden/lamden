from unittest import TestCase
from cilantro.db.utils import RedisSerializer as rs

class TestRedisSerializer(TestCase):
    def test_int_maker(self):
        self.assertEqual(rs.int(b'100'), 100)

    def test_int_maker_fail(self):
        try:
            rs.int(b'abc')
        except:
            self.assertTrue(True)

    def test_string_maker(self):
        self.assertEqual(rs.str(b'stuart'), 'stuart')