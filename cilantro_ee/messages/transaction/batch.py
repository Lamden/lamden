from cilantro_ee.messages.base.base import MessageBase
from cilantro_ee.messages.transaction.base import TransactionBase
from cilantro_ee.messages.transaction.contract import ContractTransaction, ContractTransactionBuilder
from cilantro_ee.utils import lazy_property

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
    def create(cls, transactions: List[ContractTransaction] or None):
        # Validate input
        transactions = transactions or []
        for oc in transactions:
            assert isinstance(oc, ContractTransaction), "expected transactions must be a list of ContractTransactions, " \
                                                      "but got element {}".format(oc)

        batch = transaction_capnp.TransactionBatch.new_message()
        batch.init('transactions', len(transactions))
        for i, oc in enumerate(transactions):
            batch.transactions[i] = oc._data

        return cls.from_data(batch)

    @lazy_property
    def ordered_transactions(self) -> List[ContractTransaction]:
        return [ContractTransaction.from_data(oc) for oc in self._data.transactions]

    @lazy_property
    def transactions(self) -> List[TransactionBase]:
        return self.ordered_transactions

    @property
    def is_empty(self):
        return len(self.transactions) == 0


def build_test_transaction_batch(num_tx=4):
    assert num_tx >= 0
    ordering_containers = [ContractTransactionBuilder.random_currency_tx() for _ in range(num_tx)]
    return TransactionBatch.create(ordering_containers)


