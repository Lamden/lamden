import hashlib
from cilantro.protocol.interpreters import BaseInterpreter
from cilantro.messages import TransactionBase, StandardTransaction, VoteTransaction, SwapTransaction
from cilantro.logger import get_logger

# from cilantro.nodes.delegate.db import *
from cilantro.protocol.interpreters.queries import StandardQuery, VoteQuery, SwapQuery


class VanillaInterpreter(BaseInterpreter):
    """
    A basic interpreter capable of interpreting transaction objects and performing the necessary db updates, or raising
    an exception in the case that the transactions are infeasible
    Currently supports:
        - Standard transactions
        - Vote transactions
        - Stamp transactions
        - Swap transactions
        - Redeem transactions
    """

    def __init__(self):
        super().__init__()


    def interpret_transaction(self, tx):
        """
        Interprets the transaction, and updates scratch/balance state as necessary.
        If any validation fails (i.e. insufficient balance), this method will raise an exception
        :param tx: A TestNetTransaction object to interpret
        """

