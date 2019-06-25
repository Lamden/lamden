from cilantro_ee.messages.base.base_signal import SignalBase


"""
This file defines signals used inside Delegates for inter-process (IPC) communication
"""


class MakeNextBlock(SignalBase):
    pass

class PendingTransactions(SignalBase):
    pass

class NoTransactions(SignalBase):
    pass
