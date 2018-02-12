from cilantro.db.scratch_db import ScratchDB
from cilantro.db.stamp_db import StampDB
from cilantro.db.vote_db import VoteDB
from cilantro.db.balance_db import BalanceDB
from cilantro.db.swaps_db import SwapsDB


class DBManager(object):
    def __init__(self):
        self.balance = BalanceDB()
        self.scratch = ScratchDB()
        self.votes = VoteDB()
        self.stamps = StampDB()
        self.swaps = SwapsDB()
