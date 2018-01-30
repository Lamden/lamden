from unittest import TestCase
from unittest.mock import Mock, MagicMock
from cilantro.networking.witness import Witness

class TestWitness(TestCase):
    def setUp(self):
        self.testwitness = Witness()

    def basictest(self):
        print(self.testwitness.masternodes, self.testwitness.delegates)

    def tearDown(self):
        self.testwitness.dispose()
