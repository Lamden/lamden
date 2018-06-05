import unittest
from unittest import TestCase
from cilantro.protocol.structures.bidict import Bidict


class TestBiDict(TestCase):

    def test_insert(self):
        MAX_SIZE = 1260

        bd = Bidict()
        bd['hello'] = 'world'

        self.assertEqual(bd['hello'], 'world')
        self.assertEqual(bd['world'], 'hello')

    def test_delete(self):
        MAX_SIZE = 1260

        bd = Bidict()
        bd['hello'] = 'world'

        del bd['hello']
        assert 'hello' not in bd
        assert 'world' not in bd

if __name__ == '__main__':
    unittest.main()
