from cilantro.messages.base.base import MessageBase
from cilantro.messages.transaction.contract import ContractTransaction, ContractTransactionBuilder
from cilantro.utils.lazy_property import lazy_property
from cilantro.utils.hasher import Hasher
import uuid
from enum import Enum, auto
import capnp
import transaction_capnp


class TransactionData(MessageBase):

    def validate(self):
        self.contract_tx  # validates the ContractTransaction

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return transaction_capnp.TransactionData.from_bytes_packed(data)

    @classmethod
    def create(cls, contract_tx: MessageBase, status: str, state: str):
        assert issubclass(type(contract_tx), ContractTransaction), "contract_tx must be of type ContractTransaction"
        assert type(contract_tx) in MessageBase.registry, "MessageBase class {} not found in registry {}"\
            .format(type(contract_tx), MessageBase.registry)

        data = transaction_capnp.TransactionData.new_message()
        data.contractTransaction = contract_tx._data
        data.status = status
        data.state = state
        data.contractType = MessageBase.registry[type(contract_tx)]

        return cls(data)

    @lazy_property
    def contract_tx(self) -> ContractTransaction:
        return ContractTransaction.from_data(self._data.contractTransaction)

    @property
    def status(self) -> str:
        return self._data.status

    @property
    def contract_type(self) -> type:
        return MessageBase.registry[self._data.contractType]

    @property
    def state(self) -> str:
        return self._data.state

    @lazy_property
    def hash(self):
        return Hasher.hash(self)

    def __hash__(self):
        return int(self.hash,16)

class TransactionDataBuilder:
    @classmethod
    def create_random_tx(cls, status='SUCCESS', state='SET x 1'):
        return TransactionData.create(
            contract_tx=ContractTransactionBuilder.random_currency_tx(), status=status, state=state
        )
