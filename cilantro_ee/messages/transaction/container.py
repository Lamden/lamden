from cilantro_ee.messages.base.base import MessageBase
from cilantro_ee.messages.transaction.base import TransactionBase
from cilantro_ee.messages.transaction.contract import ContractTransaction
import capnp
import transaction_capnp


class TransactionContainer(MessageBase):
    """
    Transaction containers package transaction data from users by simply including a 'type' field that is used to
    lookup the type to deserialize. ATM transaction containers are only used to wrap up POST requests to masternode.
    """

    def validate(self):
        pass

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return transaction_capnp.TransactionContainer.from_bytes_packed(data)

    @classmethod
    def create(cls, tx: TransactionBase):
        # assert issubclass(type(tx), TransactionBase), "TransactionContainer data must be a TransactionBase subclass"
        # assert type(tx) in MessageBase.registry, "MessageBase class {} not found in registry {}"\
        #     .format(type(tx), MessageBase.registry)

        container = transaction_capnp.TransactionContainer.new_message()
        container.type = 0
        container.payload = tx.serialize()

        return cls(container)

    def open(self, validate=True) -> TransactionBase:
        """
        Deserializes the message packed inside the envelope and returns it
        :param validate: If we should call .validate() after deserializing the message
        :return: The deserialized TransactionBase instance
        """

        return ContractTransaction.from_bytes(self._data.payload, validate=validate)