from cilantro.messages import MessageBase
from cilantro.protocol.structures import MerkleTree




class BlockDataRequest(MessageBase):
    """
    BlockData requests/replies are used to transfer transactions from a block between masternode/delegate.

    When Masternode is attempting to publish a new block, it creates a BlockDataRequest to request a single transaction from
    a delegate by specifying the transaction's hash.

    A delegate receives a BlockDataRequest, and creates a BlockDataReply including the binary for the specified transaction.

    TODO -- switch this class to use capnp
    """

    def validate(self):
        pass

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return data

    def serialize(self):
        return self._data

    @classmethod
    def create(cls, tx_hash: str):
        # TODO -- validate tx_hash is valid 64 char hex
        return cls.from_data(tx_hash)

    @property
    def tx_hash(self) -> str:
        """
        The hash of the transaction to request (64 characters, valid hex)
        """
        return self._data


class BlockDataReply(MessageBase):
    """
    BlockDataReply acts as a holder for an individual transaction. They are requested from delegates by Masternodes when
    a Masternode needs to retrieve the block data associated with a BlockContender
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
    def raw_tx(self) -> bytes:
        """
        The raw data for the requested transaction, as bytes
        """
        return self._data

    @property
    def tx_hash(self) -> str:
        """
        The hash of the requested transaction (64 characters, valid hex)
        """
        return MerkleTree.hash(self._data)