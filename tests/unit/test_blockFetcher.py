from unittest import TestCase
from cilantro_ee.services.block_fetch import BlockFetcher


class TestBlockFetcher(TestCase):
    def test_init(self):
        b = BlockFetcher()

    def test_get_missing_block_index(self):
        pass
