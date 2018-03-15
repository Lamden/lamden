from cilantro.db.delegate.scratch_driver import ScratchDriver
from cilantro.db.delegate.stamps_driver import StampsDriver
from cilantro.db.delegate.votes_driver import VotesDriver
from cilantro.db.delegate.balance_driver import BalanceDriver
from cilantro.db.delegate.swaps_driver import SwapsDriver
from cilantro.logger import get_logger

class DriverManager(object):
    def __init__(self, db=0):
        self.log = get_logger("DB-#{}".format(db))
        self.log.info("Configuring DB #{}".format(db))

        self.balance = BalanceDriver(db=db)
        self.scratch = ScratchDriver(db=db)
        self.votes = VotesDriver(db=db)
        self.stamps = StampsDriver(db=db)
        self.swaps = SwapsDriver(db=db)

    def flush_state(self):
        print("Flushing balance")
        self.balance.flush()
        print("Flushing scratch")
        self.scratch.flush()
        print("Done flushing state")