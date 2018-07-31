from cilantro.nodes.delegate.delegate import Delegate, DelegateBaseState
from cilantro.storage.db import DB
from cilantro.messages.transaction.ordering import OrderingContainer
from cilantro.constants.nodes import max_queue_size
from cilantro.protocol.states.decorators import input, enter_from_any, exit_to_any, exit_to

DelegateBootState = "DelegateBootState"
DelegateInterpretState = "DelegateInterpretState"
DelegateConsensusState = "DelegateConsensusState"
DelegateCatchupState = "DelegateInterpretState"


@Delegate.register_state
class DelegateInterpretState(DelegateBaseState):
    """
    Delegate interpret state has the delegate receive and interpret that transactions are valid according to the
    interpreter chosen. Once the number of transactions in the queue exceeds the size or a time interval is reached the
    delegate moves into consensus state
    """

    @enter_from_any
    def enter_from_any(self, prev_state):
        self.log.debug("Flushing pending tx queue of {} txs".format(len(self.parent.pending_txs)))
        for tx in self.parent.pending_txs:
            self.interpret_tx(tx)
        self.parent.pending_txs = []

        # (for debugging) TODO remove
        with DB() as db:
            r = db.execute('select * from state_meta')
            results = r.fetchall()
            self.log.critical("LATEST STATE INFO: {}".format(results))

    @exit_to_any
    def exit_any(self, next_state):
        # Flush queue if we are not leaving interpreting for consensus
        self.log.warning("Delegate exiting interpreting for state {}, flushing queue".format(next_state))
        self.parent.interpreter.flush(update_state=False)

    @exit_to(DelegateConsensusState)
    def exit_to_consensus(self):
        pass

    @input(OrderingContainer)
    def handle_tx(self, tx: OrderingContainer):
        self.interpret_tx(tx=tx)

    def interpret_tx(self, tx: OrderingContainer):
        self.parent.interpreter.interpret(tx)

        self.log.debug("Size of queue: {}".format(len(self.parent.interpreter.queue)))

        if self.parent.interpreter.queue_size >= max_queue_size:
            self.log.info("Consensus time!")
            self.parent.transition(DelegateConsensusState)
        else:
            self.log.debug("Not consensus time yet, queue is only size {}/{}"
                           .format(self.parent.interpreter.queue_size, max_queue_size))
