from cilantro.protocol.statemachine import State, receive
from cilantro.messages import StandardTransaction, VoteTransaction, SwapTransaction, TransactionBase


class BaseState(State):

    @receive(StandardTransaction)
    def base_recv_std(self, tx: StandardTransaction):
        pass

    @receive(TransactionBase)
    def base_recv_tx(self, tx: TransactionBase):
        pass

    @receive(VoteTransaction)
    def base_recv_vote(self, tx: VoteTransaction):
        pass


class SubState(BaseState):
    @receive(VoteTransaction)
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
