from cilantro.messages import TransactionBase
from cilantro.logger import get_logger
from collections import deque
from cilantro.db import ScratchCloningVisitor, DB
from sqlalchemy.sql import Update
from cilantro.protocol.interpreters.queries import *


class VanillaInterpreter:
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
        self.log = get_logger("Interpreter")
        self.log.info("Creating interpreter object")
        self.queue = deque()

    def flush(self, update_state=True):
        """
        Flushes internal queue and resets scratch. If update_state is True, then this also interprets its transactions
        against state
        """
        self.log.info("Flushing queue with update_state={} for {} items".format(update_state, len(self.queue)))

        if update_state:
            self.log.debug("Updating state...")
            # TODO -- implement
            # for query in self.queue:
            #     tables.db.execute(query)
            self.log.debug("Done updating state")

        # TODO -- flush scratch
        self.queue.clear()

    def get_queue_binary(self) -> list:
        return [row[0].serialize() for row in self.queue]

    def interpret_transaction(self, tx):
        """
        Interprets the transaction, and updates scratch/balance state as necessary.
        If any validation fails (i.e. insufficient balance), this method will raise an exception
        :param tx: A TestNetTransaction object to interpret
        """
        self.log.debug("Interpreting tx {}".format(tx))
        assert issubclass(type(tx), TransactionBase), "Transaction type {} is not a subclass of TransactionBase" \
            .format(type(tx))

        queries = tx.interpret(compile_deltas=False)

        if not queries:
            self.log.error("\n!!! Error interpreting tx {}\n".format(tx))
            return

        self.log.debug("Got queries {} for tx {}".format(queries, tx))
        self.queue.append((tx, *queries))

        for q in queries:
            self.log.debug("About to get scratch query for query {}".format(q))
            scratch_q = ScratchCloningVisitor().traverse(q)

            with DB() as db:
                if scratch_q.__class__ == Update:
                    scratch_q.table = db.tables.mapping[scratch_q.table]
                db.execute(scratch_q)



