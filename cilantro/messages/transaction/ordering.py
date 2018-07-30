from cilantro.messages.base.base import MessageBase
from cilantro.messages.transaction.base import TransactionBase
from cilantro.db import VKBook

import capnp
import transaction_capnp
import time

from cilantro.logger import get_logger
log = get_logger(__name__)

class OrderingContainer(MessageBase):
    """
    Transaction containers package transaction data from users by simply including a 'type' field that is used to
    lookup the type to deserialize. ATM transaction containers are only used to wrap up POST requests to masternode.
    """

    def validate(self):
        assert self.masternode_vk in VKBook.get_masternodes(), 'Not a masternode VK'

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return transaction_capnp.OrderingContainer.from_bytes_packed(data)

    @classmethod
    def create(cls, tx: TransactionBase, masternode_vk: str):
        container = transaction_capnp.OrderingContainer.new_message()
        container.type = MessageBase.registry[type(tx)]
        container.transaction = tx.serialize()
        container.masternodeVk = masternode_vk
        container.utcTimeMs = int(time.time()*1000)
        return cls(container)

    @property
    def masternode_vk(self) -> str:
        return self._data.masternodeVk.decode()

    @property
    def utc_time(self, mode='ms'):
        if mode == 'ms':
            return self._data.utcTimeMs
        elif mode == 's':
            return self._data.utcTimeMs/1000.0

    @property
    def transaction(self):
        assert self._data.type in MessageBase.registry, "Type {} not found in registry {}"\
            .format(self._data.type, MessageBase.registry)

        return MessageBase.registry[self._data.type].from_bytes(self._data.transaction)
