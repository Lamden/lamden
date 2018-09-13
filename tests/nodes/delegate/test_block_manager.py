from unittest import TestCase
from cilantro.constants.testnet import TESTNET_DELEGATES
from cilantro.nodes.delegate.block_manager import BlockManager


class TestBlockManager(TestCase):

    def test_init(self):
        ip = '127.0.0.1'
        sk = TESTNET_DELEGATES[0]['sk']

        bm = BlockManager(ip=ip, signing_key=sk)


if __name__ == "__main__":
    import unittest
    unittest.main()
