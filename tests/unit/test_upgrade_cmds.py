import argparse
import unittest
from cilantro_ee.nodes.commands.cmd import setup_cilparser, Cilparser


class ParserTest(unittest.TestCase):

    def setUp(self):
        self.parser = argparse.ArgumentParser(description = "cmd test", prog = 'test_cil')
        setup_cilparser(self.parser)

    def tearDown(self):
        self.parser = None

    def test_upd_parser(self):
        args = self.parser.parse_args(['update'])
        dict = args.__dict__

        print(dict)
        self.assertEqual(len(dict), 3)
        self.assertEqual(dict['pkg_hash'], None)
        self.assertEqual(dict['vote'], False)
        self.assertEqual(dict['ready'], False)

    def test_update_trigger(self):
        args = self.parser.parse_args(['update', '-t', 'new_pepper'])
        dict = args.__dict__

        print(dict)

        self.assertEqual(dict['pkg_hash'], 'new_pepper')
        self.assertEqual(dict['vote'], False)
        self.assertEqual(dict['ready'], False)

    def test_update_vote(self):
        args = self.parser.parse_args(['update', '-v'])
        dict = args.__dict__
        self.assertEqual(dict['pkg_hash'], None)
        self.assertEqual(dict['vote'], True)
        self.assertEqual(dict['ready'], False)

    def test_update_ready(self):
        args = self.parser.parse_args(['update', '-v'])
        dict = args.__dict__
        self.assertEqual(dict['pkg_hash'], None)
        self.assertEqual(dict['vote'], False)
        self.assertEqual(dict['ready'], True)


if __name__ == '__main__':
    unittest.main()
