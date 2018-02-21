from cilantro.db.delegate.scratch_driver import ScratchDriver
from cilantro.db.delegate.stamps_driver import StampsDriver
from cilantro.db.delegate.votes_driver import VotesDriver
from cilantro.db.delegate.balance_driver import BalanceDriver
from cilantro.db.delegate.swaps_driver import SwapsDriver


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