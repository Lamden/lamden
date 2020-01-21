import argparse

from unittest import TestCase
from cilantro_ee.nodes.commands.cmd import setup_cilparser, Cilparser


class ParserTest(TestCase):

    def setup(self):
        parser = argparse.ArgumentParser(description = "cmd test", prog = 'test_cil')
        setup_cilparser(parser)
        args = parser.parse_args()

        self.assertEqual(args.vote, False)
        self.assertEqual(args.read, False)

    def test_update_trigger(self):
        pass

    def test_update_vote(self):
        pass

    def test_update_ready(self):
        pass

