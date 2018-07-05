from cilantro.messages import MessageBase, TransactionBase

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
        assert issubclass(type(tx), MessageBase), "TransactionContainer data must be a TransactionBase subclass"
        # assert type(tx) in MessageBase.registry, "MessageBase class {} not found in registry {}"\
        #     .format(type(tx), MessageBase.registry)

        container = transaction_capnp.TransactionContainer.new_message()
        container.type = MessageBase.registry[type(tx)]
        container.payload = tx.serialize()

        return cls(container)

    def open(self, validate=True) -> TransactionBase:
        """
        Deserializes the message packed inside the envelope and returns it
        :param validate: If we should call .validate() after deserializing the message
        :return: The deserialized TransactionBase instance
        """
        assert self._data.type in MessageBase.registry, "MessageBase type {} not found in registry {}"\
                                                        .format(self._data.type, MessageBase.registry)
        return MessageBase.registry[self._data.type].from_bytes(self._data.payload, validate=validate)