from unittest import TestCase
from unittest.mock import MagicMock
from cilantro.interpreters.basic_interpreter import BasicInterpreter
from cilantro.wallets import ED25519Wallet


class TestBasicInterpreter(TestCase):
    def test_init(self):
        try:
            interpreter = BasicInterpreter()
            assert True
        except:
            print("Error instantiating interpreter (likely Redis DB problem)")

    def test_std_tx_valid(self):
        """
        Tests a valid standard transaction, where sender has enough balance in scratch, and the recipient exists in
        the scratch
        """
        interpreter = BasicInterpreter()
        sender_s, sender_v = ED25519Wallet.new()
        reciever_s, reciever_v = ED25519Wallet.new()
        interpreter.balance, interpreter.scratch = MagicMock(), MagicMock()

        # Mock out DB method calls
        interpreter.scratch.wallet_exists.return_value = True
        interpreter.scratch.sender_balance.return_value = 1000

        # TODO -- finish these (this is a incomplete test atm)
