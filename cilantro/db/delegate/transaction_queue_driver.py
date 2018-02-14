from cilantro.db.delegate.driver_base import DriverBase
from cilantro.db.constants import QUEUE_KEY
from cilantro.db.utils import RedisSerializer as RS
from typing import Generator, List


class TransactionQueueDriver(DriverBase):

    def enqueue_transaction(self, transaction_payload: tuple):
        """
        Adds a new transaction to the end of the queue
        :param transaction_payload: A tuple specifying the transaction data
        :return:
        """
        # Below behavior reduces queue size, but will only work if we add UUIDs to transactions
        # tx_key = RS.hash_tuple(transaction_payload)
        # self.r.hset(TRANSACTION_KEY, tx_key, RS.str_from_tuple(transaction_payload))
        # self.r.rpush(QUEUE_KEY, tx_key)

        self.r.rpush(QUEUE_KEY, RS.str_from_tuple(transaction_payload))

    def dequeue_transaction(self) -> tuple:
        """
        Removes the front transaction from the queue and returns it
        :return: A tuple specifying the transaction data
        """
        # See comment in enqueue_transaction
        # tx_key = self.r.lpop(QUEUE_KEY)
        # tx_val = self.r.hget(TRANSACTION_KEY)
        # self.r.hdel(TRANSACTION_KEY, tx_key)
        # return RS.tuple_from_str(tx_val)

        return RS.tuple_from_str(RS.str(self.r.lpop(QUEUE_KEY)))

    def empty_queue_iter(self) -> Generator[tuple, None, None]:
        """
        Returns a generator that yields all transactions in the queue, in FIFO order. This dequeues transactions at
        each yield. Note: this will empty the queue as it iterates over
        :return: A generator object that yields the transactions in the queue as tuples
        """
        size = self.queue_size()
        while size > 0:
            yield self.dequeue_transaction()
            size -= 1

    def empty_queue(self) -> List[tuple]:
        """
        Flushes the queue and returns all transactions as a list in FIFI order
        :return: A list containing all the transaction tuples in the queue in FIFO order
        """
        queues = []
        size = self.queue_size()
        for _ in range(size):
            queues.append(self.dequeue_transaction())
        return queues

    def queue_size(self) -> int:
        """
        Returns the number of transactions in the queue
        :return: An integer specifying the number of transactions in the queue
        """
        return self.r.llen(QUEUE_KEY)
