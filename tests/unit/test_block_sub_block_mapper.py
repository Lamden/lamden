from unittest import TestCase
from cilantro_ee.crypto import BlockSubBlockMapper


class TestBlockSubBlockMapper(TestCase):
    def test_init(self):
        b = BlockSubBlockMapper()
