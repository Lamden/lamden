from cilantro.protocol.statemachine import State, recv
from cilantro.messages import StandardTransaction, VoteTransaction, SwapTransaction, TransactionBase


class BaseState(State):

    @recv(StandardTransaction)
    def base_recv_std(self, tx: StandardTransaction):
        pass

    @recv(TransactionBase)
    def base_recv_tx(self, tx: TransactionBase):
        pass

    @recv(VoteTransaction)
    def base_recv_vote(self, tx: VoteTransaction):
        pass


class SubState(BaseState):
    @recv(VoteTransaction)
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