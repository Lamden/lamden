from cilantro.messages import MessageBase
from cilantro.protocol.structures import MerkleTree

"""
BlockData requests/replies are used to transfer transactions from a block between masternode/delegate. 

When Masternode is attempting to publish a new block, it creates a BlockDataRequest to request a single transaction from
a delegate by specifying the transaction's hash.

A delegate receives a BlockDataRequest, and creates a BlockDataReply including the binary for the specified transaction.

TODO -- switch this class to use capnp
"""


class BlockDataRequest(MessageBase):
    def validate(self):
        pass

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return data

    def serialize(self):
        return self._data

    @classmethod
    def create(cls, tx_hash: bytes):
        return cls.from_data(tx_hash)

    @property
    def tx_hash(self):
        return self._data


class BlockDataReply(MessageBase):
    """
    Underlying _data is just a binary blob storing a serialized transaction
    """
    def validate(self):
        pass

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return data

    def serialize(self):
        return self._data

    @classmethod
    def create(cls, tx_binary: bytes):
        return cls.from_data(tx_binary)

    @property
    def raw_tx(self):
        return self._data

    @property
    def tx_hash(self):
        return MerkleTree.hash(self._data)