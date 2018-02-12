from cilantro.db.base_db import BaseDB
from cilantro.db.constants import VOTE_KEY
from cilantro.db.utils import RedisSerializer as RS

class VoteDB(BaseDB):

    def get_votes(self, candidate_key: str) -> int:
        """
        Retrieves the votes for a candidate
        :param candidate_key: The verifying address of the candidate
        :return: An integer representing the total votes for a candidate
        """
        if self.r.hexists(VOTE_KEY, candidate_key):
            return RS.int(self.r.hget(VOTE_KEY, candidate_key))
        else:
            return 0

    def