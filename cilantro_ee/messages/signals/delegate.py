from cilantro_ee.messages.base.base_signal import SignalBase


"""
This file defines signals used inside Delegates for inter-process (IPC) communication
"""


class MakeNextBlock(SignalBase):
    pass


class DiscardPrevBlock(SignalBase):
    pass
