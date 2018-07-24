from cilantro.messages import MessageBase, TransactionBase
from cilantro.db import VKBook

import capnp
import transaction_capnp
import time


class OrderingContainer(MessageBase):
    """
    Transaction containers package transaction data from users by simply including a 'type' field that is used to
    lookup the type to deserialize. ATM transaction containers are only used to wrap up POST requests to masternode.
    """

    def validate(self):
        assert self._data.masternodeVk in VKBook.get_masternodes(), 'Not a masternode VK'

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return transaction_capnp.OrderingContainer.from_bytes_packed(data)

    @classmethod
    def create(cls, tx: TransactionBase, masternode_vk: str):
        container = transaction_capnp.OrderingContainer.new_message()
        container.type = MessageBase.registry[type(tx)]
        container.payload = tx.serialize()
        container.masternodeVk = masternode_vk
        container.utcTime = int(time.time()*1000)
        return cls(container)

    @property
    def masternode_vk() -> str:
        return self._data.masternodeVk.decode()

    @property
    def utc_time(mode='ms'):
        if mode == 'ms':
            return self._data.utcTime
        elif mode == 's':
            return self._data.utcTime/1000.0
