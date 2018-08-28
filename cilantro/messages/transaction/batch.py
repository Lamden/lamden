from cilantro.messages.base.base import MessageBase
from cilantro.messages.transaction.ordering import OrderingContainer
from cilantro.utils import lazy_property

from typing import List

import capnp
import transaction_capnp


class TransactionBatch(MessageBase):

    def validate(self):
        # TODO implement
        pass

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return transaction_capnp.TransactionBatch.from_bytes_packed(data)

    @classmethod
    def create(cls, transactions: List[OrderingContainer] or None):
        # Validate input
        transactions = transactions or []
        for oc in transactions:
            assert isinstance(oc, OrderingContainer), "expected transactions must be a list of OrderingContains, " \
                                                      "but got element {}".format(oc)

        batch = transaction_capnp.TransactionBatch.new_message()
        batch.init('transactions', len(transactions))
        for i, oc in enumerate(transactions):
            batch.transactions[i] = oc._data

        return cls.from_data(batch)

    @lazy_property
    def transactions(self) -> List[OrderingContainer]:
        return [OrderingContainer.from_data(oc) for oc in self._data.transactions]

    @property
    def is_empty(self):
        return len(self.transactions) == 0
