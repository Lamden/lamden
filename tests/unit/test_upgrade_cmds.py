import argparse

import unittest
from cilantro_ee.nodes.commands.cmd import setup_cilparser, Cilparser


class ParserTest(unittest.TestCase):

    def setUp(self):
        parser = argparse.ArgumentParser(description = "cmd test", prog = 'test_cil')
        setup_cilparser(parser)
        args = parser.parse_args()


        # self.assertEqual(args.vote, False)
        # self.assertEqual(args.read, False)
        print('hello')

    def test_update_trigger(self):
        print('hello')
        pass

    def test_update_vote(self):
        pass

    def test_update_ready(self):
        pass


if __name__ == '__main__':
    unittest.main()
