import redis
from cilantro.db.base_db import BaseDB

class TransactionQueueDB(BaseDB):

    def __init__(self, host='localhost', port=6379, db=0):
        super().__init__(host, port, db)

    def enqueue_transaction(self, transaction_payload: tuple):
        """
        Adds a new transaction to the end of the queue
        :param transaction_payload: A tuple specifying the transaction data
        :return:
        """
        # TODO -- implement

    def dequeue_transaction(self) -> tuple:
        """
        Removes the front transaction from the queue and returns it
        :return: A tuple specifying the transaction data
        """
        # TODO -- implement

    def queue_size(self) -> int:
        """
        Returns the number of transactions in the queue
        :return: An integer specifying the number of transactions in the queue
        """
        # TODO -- implement
        return 5