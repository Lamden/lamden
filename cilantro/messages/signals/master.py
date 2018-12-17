from cilantro.messages.base.base_signal import SignalBase


"""
This file defines signals used inside Masternode for inter-process (IPC) communication
"""


class EmptyBlockMade(SignalBase):
    pass

class NonEmptyBlockMade(SignalBase):
    pass

