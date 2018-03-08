from cilantro.nodes.delegate.db.scratch_driver import ScratchDriver
from cilantro.nodes.delegate.db.stamps_driver import StampsDriver
from cilantro.nodes.delegate.db import VotesDriver
from cilantro.nodes.delegate.db import BalanceDriver
from cilantro.nodes.delegate.db import SwapsDriver


class DriverManager(object):
    def __init__(self):
        self.balance = BalanceDriver()
        self.scratch = ScratchDriver()
        self.votes = VotesDriver()
        self.stamps = StampsDriver()
        self.swaps = SwapsDriver()

    def flush_state(self):
        print("Flushing balance")
        self.balance.flush()
        print("Flushing scratch")
        self.scratch.flush()
        print("Done flushing state")