import unittest
from unittest import TestCase
from unittest.mock import MagicMock, patch
from cilantro.nodes.masternode.block_aggregator import BlockAggregator
from cilantro.protocol import wallet as W

SK, VK = W.new()

class TestBlockAggregator(TestCase):

    def test_run(self):
        """
        Tests that receiving a block contender in RunState pushes the SM into NewBlockState
        """
        ba = BlockAggregator(ip='127.0.0.1', signing_key=SK)
        print(ba.sub, ba.pub)

if __name__ == '__main__':
    unittest.main()
