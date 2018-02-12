from cilantro.db.base_db import BaseDB
from cilantro.db.constants import QUEUE_KEY, TRANSACTION_KEY
from cilantro.db.utils import RedisSerializer as RS

import json
import hashlib

class TransactionQueueDB(BaseDB):

    def enqueue_transaction(self, transaction_payload: tuple):
        """
        Adds a new transaction to the end of the queue
        :param transaction_payload: A tuple specifying the transaction data
        :return:
        """
        tx_key = RS.hash_tuple(transaction_payload)
        self.r.hset(TRANSACTION_KEY, tx_key, RS.str_from_tuple(transaction_payload))
        self.r.rpush(QUEUE_KEY, tx_key)

    def dequeue_transaction(self) -> tuple:
        """
        Removes the front transaction from the queue and returns it
        :return: A tuple specifying the transaction data
        """
        tx_key = self.r.lpop(QUEUE_KEY)
        tx_val = self.r.hget(TRANSACTION_KEY)
        self.r.hdel(TRANSACTION_KEY, tx_key)
        return RS.tuple_from_str(tx_val)

    def queue_size(self) -> int:
        """
        Returns the number of transactions in the queue
        :return: An integer specifying the number of transactions in the queue
        """
        return self.r.llen(QUEUE_KEY)
