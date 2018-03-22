import hashlib
from cilantro.protocol.interpreters import BaseInterpreter
from cilantro.messages import TransactionBase, StandardTransaction, VoteTransaction, SwapTransaction
from cilantro.logger import get_logger

# from cilantro.nodes.delegate.db import *
from cilantro.protocol.interpreters.queries import LevelDBBackend, StandardQuery, SCRATCH, VoteQuery, SwapQuery


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

    def __init__(self, backend=LevelDBBackend()):
        super().__init__()

        self.backend = backend
        self.log = get_logger("Delegate.Interpreter hooked up.")

        self.log.debug("Interpreter flushing scratch...")
        self.backend.flush(SCRATCH)
        self.tx_method = {
            StandardTransaction: StandardQuery,
            VoteTransaction: VoteQuery,
            SwapTransaction: SwapQuery
        }

    def interpret_transaction(self, tx: TransactionBase):
        """
        Interprets the transaction, and updates scratch/balance state as necessary.
        If any validation fails (i.e. insufficient balance), this method will raise an exception
        :param tx: A TestNetTransaction object to interpret
        """
        self.log.debug("Interpreter got tx: {}".format(tx))

        results = None

        try:
            results = self.tx_method[type(tx)](backend=self.backend).process_tx(tx)
        except Exception as e:
            self.log.error("Got Transaction of unkown type: {}, {}".format(type(tx), e))

        self.log.debug("Results of interpretation: {}".format(results))
