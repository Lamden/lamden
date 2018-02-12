from cilantro.db.base_db import BaseDB
from cilantro.db.constants import VOTE_KEY, VOTE_TYPES
from cilantro.db.utils import RedisSerializer as RS


class VoteDB(BaseDB):
    def get_votes(self, candidate_key: str, variable_name: str) -> int:
        """
        Retrieves the all votes for the candidate
        :param candidate_key: The verifying address of the candidate
        :param variable_name: The name of the metavariable that is being voted on in VOTE_TYPES
        :return: An integer representing the total votes for a candidate
        """
        # TODO -- implement
        raise NotImplementedError

    def set_vote(self, candidate_key: str, vote_value: str, variable_name: str, is_numeric=False):
        """
        Sets the candidate_key's vote to vote_value
        :param candidate_key: The verifying address of the candidate
        :param vote_value: The value of candidate_key's vote
        :param variable_name: The name of the metavariable that is being voted on (ie. 'DELEGATE')
        :param is_numeric: A boolean specifying if the metavariable being voted on is numeric
        """
        # TODO -- implement candidate vote sets for fast tallying
        self.r.hset(VOTE_KEY + '_' + variable_name, candidate_key, vote_value)
