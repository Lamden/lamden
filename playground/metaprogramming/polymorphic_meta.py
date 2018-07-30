from cilantro.protocol.statemachine.state import State
from cilantro.protocol.statemachine.decorators import input
from cilantro.messages.transaction.standard import StandardTransaction
from cilantro.messages.transaction.vote import VoteTransaction
from cilantro.messages.transaction.base import TransactionBase

class BaseState(State):

    @input(StandardTransaction)
    def base_recv_std(self, tx: StandardTransaction):
        pass

    @input(TransactionBase)
    def base_recv_tx(self, tx: TransactionBase):
        pass

    @input(VoteTransaction)
    def base_recv_vote(self, tx: VoteTransaction):
        pass


class SubState(BaseState):
    @input(VoteTransaction)
    def recv_vote(self, tx: VoteTransaction):
        pass

if __name__ == "__main__":
    print("BaseState receivers:")
    for k, v in BaseState._receivers.items():
        print("\t {}: {}".format(k, v))
    print("-------------------")
    print("SubState receivers:")
    for k, v in SubState._receivers.items():
        print("\t {}: {}".format(k, v))