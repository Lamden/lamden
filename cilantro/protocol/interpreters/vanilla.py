import hashlib
from cilantro.protocol.interpreters import BaseInterpreter
from cilantro.messages import TransactionBase, StandardTransaction
from cilantro.logger import get_logger

# from cilantro.nodes.delegate.db import *
from cilantro.db.delegate import LevelDBBackend, StandardQuery, SCRATCH


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

    def interpret_transaction(self, tx: TransactionBase):
        """
        Interprets the transaction, and updates scratch/balance state as necessary.
        If any validation fails (i.e. insufficient balance), this method will raise an exception
        :param tx: A TestNetTransaction object to interpret
        """
        self.log.debug("Interpreter got tx: {}".format(tx))

        if tx.__class__ == StandardTransaction:
            self.interpret_std_tx(tx)
        else:
            self.log.error("Got Transaction of unkown type: {}".format(type(tx)))

    def interpret_std_tx(self, tx: StandardTransaction):
        self.log.debug("Interpreter got tx with data sender={}, receiver={}, amount={}"
                       .format(tx.sender, tx.receiver, tx.amount))

        tx, sender_changes, receiver_changes = StandardQuery(backend=self.backend).process_tx(tx)

        if tx is None:
            raise Exception("Standard Tx Error")