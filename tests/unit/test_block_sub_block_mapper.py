from unittest import TestCase
from cilantro_ee.core.crypto.block_sub_block_mapper import BlockSubBlockMapper


class TestBlockSubBlockMapper(TestCase):
    def test_init(self):
        b = BlockSubBlockMapper()
