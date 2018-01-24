from unittest import TestCase
from cilantro.networking import Witness

class TestWitness(TestCase):
    w = Witness("tcp://*:5558", "tcp://localhost:5559")
    print(w.masternodes, w.delegates)
