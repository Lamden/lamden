from cilantro.nodes.delegate import DelegateConsensusState
from cilantro.utils.hasher import Hasher
from cilantro.messages import *
from unittest import TestCase
from unittest.mock import Mock


class TestConsensus(TestCase):

    def test_tx_request_replies_with_correct_data(self):
        """
        Tests that a delegate who receives a TransactionRequest in Consensus state replies with the correct data
        """
        pass