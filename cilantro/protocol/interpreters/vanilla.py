from cilantro.messages import TransactionBase
from cilantro.logger import get_logger
from collections import deque
from cilantro.db import ScratchCloningVisitor, DB
from sqlalchemy.sql import Update
from cilantro.protocol.interpreters.queries import *
import itertools


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
            queries = itertools.chain(*[row[1:] for row in self.queue])
            self.log.info("got queries to execute: {}".format(str(queries)))

            with DB() as db:
                for q in queries:
                    qt = q.compile(compile_kwargs={'literal_binds': True})
                    self.log.debug("executing query {}".format(qt))
                    db.execute(q)
            # TODO -- implement
            # for query in self.queue:
            #     tables.db.execute(query)
            self.log.debug("Done updating state")

        # Drop scratch
        with DB() as db:
            # NOTE -- this just drops the scratch version of 'balances' for now. If interpretation of tx's were to
            #  operate on other tables, (and consequently other scratch tables), these would need to be dropped as well.
            q = delete(db.tables.mapping[db.tables.balances])
            self.log.critical("\n attemtpign to executing query {}".format(q))
            db.execute(q)

        self.queue.clear()

    def get_queue_binary(self) -> list:
        return [row[0].serialize() for row in self.queue]

    @property
    def queue_len(self):
        return len(self.queue)

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

            # TODO move context manager outside of loop
            with DB() as db:
                if scratch_q.__class__ == Update:
                    scratch_q.table = db.tables.mapping[scratch_q.table]
                db.execute(scratch_q)



