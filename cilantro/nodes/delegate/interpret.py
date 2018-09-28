# from cilantro.nodes.delegate.delegate import Delegate, DelegateBaseState
# from cilantro.storage.blocks import BlockStorageDriver
# from cilantro.messages.transaction.ordering import OrderingContainer
# from cilantro.constants.nodes import TRANSACTIONS_PER_SUB_BLOCK
# from cilantro.protocol.states.decorators import input, enter_from_any, exit_to_any, exit_to, enter_from
# from cilantro.utils.lprocess import LProcess
# from cilantro.nodes.delegate.block_manager import BlockManager
#
# DelegateBootState = "DelegateBootState"
# DelegateInterpretState = "DelegateInterpretState"
# DelegateConsensusState = "DelegateConsensusState"
# DelegateCatchupState = "DelegateCatchupState"
#
#
# @Delegate.register_state
# class DelegateInterpretState(DelegateBaseState):
#     """
#     Delegate interpret state has the delegate receive and interpret that transactions are valid according to the
#     interpreter chosen. Once the number of transactions in the queue exceeds the size or a time interval is reached the
#     delegate moves into consensus state
#     """
#
#     def _general_entry(self):
#         self.parent.current_hash = BlockStorageDriver.get_latest_block_hash()
#         self.log.notice("Delegate entering interpret state with current block hash {}".format(self.parent.current_hash))
#
#         # TODO find a way to properly integrate the BlockManager in this state machine framework
#         # DEBUG TODO DELETE
#         self.log.important("Delegate starting BlockManager process and blocking!")
#         bm = LProcess(target=BlockManager, kwargs={'signing_key': self.parent.signing_key, 'ip': self.parent.ip})
#         bm.start()
#         bm.join()  # Block for now
#         # END DEBUG
#
#     def _reset_queue(self):
#         self.log.notice("Emptying transaction queue of {} items".format(len(self.parent.pending_txs)))
#         self.parent.pending_txs.clear()
#
#         self.log.notice("Flushing interpreting without updating")
#         self.parent.interpreter.flush(update_state=False)
#
#     @enter_from_any
#     def enter_any(self, prev_state):
#         self._general_entry()
#         self._reset_queue()
#
#     @enter_from(DelegateConsensusState)
#     def enter_from_consensus(self):
#         self._general_entry()
#
#         # If we just entered from Consensus, interpret all pending transactions up to MaxQueueSize
#         num_to_pop = min(len(self.parent.pending_txs), TRANSACTIONS_PER_SUB_BLOCK)
#         self.log.notice("Flushing {} txs from total {} pending txs".format(num_to_pop, len(self.parent.pending_txs)))
#         for _ in range(num_to_pop):
#             self.interpret_tx(self.parent.pending_txs.popleft())
#
#     @exit_to_any
#     def exit_any(self, next_state):
#         # Flush queue if we are not leaving interpreting for consensus
#         self._reset_queue()
#
#     @exit_to(DelegateConsensusState)
#     def exit_to_consensus(self):
#         pass
#
#     @input(OrderingContainer)
#     def handle_tx(self, tx: OrderingContainer):
#         assert len(self.parent.pending_txs) == 0, "Interpret state should only be handling txs if pending_txs is empty!"
#         self.interpret_tx(tx=tx)
#
#     def interpret_tx(self, tx: OrderingContainer):
#         self.parent.interpreter.interpret(tx)
#         self.log.debugv("Current size of transaction queue: {}".format(len(self.parent.interpreter.queue)))
#
#         if self.parent.interpreter.queue_size == TRANSACTIONS_PER_SUB_BLOCK:
#             self.log.success("Consensus time! Delegate has {} tx in queue.".format(self.parent.interpreter.queue_size))
#             self.parent.transition(DelegateConsensusState)
#             return
#
#         elif self.parent.interpreter.queue_size > TRANSACTIONS_PER_SUB_BLOCK:
#             self.log.fatal("Delegate exceeded max queue size! How did this happen!!!")
#             raise Exception("Delegate exceeded max queue size! How did this happen!!!")
#
#         else:
#             self.log.debug("Not consensus time yet, queue is only size {}/{}"
#                            .format(self.parent.interpreter.queue_size, TRANSACTIONS_PER_SUB_BLOCK))
