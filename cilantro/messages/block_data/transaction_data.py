from cilantro.messages import MessageBase, ContractTransaction
from cilantro.utils import lazy_property, Hasher
from typing import List


# TODO switch this class to use capnp, and also
class TransactionRequest(MessageBase):
    """
    BlockData requests/replies are used to transfer transactions from a block between masternode/delegate.

    When Masternode is attempting to publish a new block, it creates a TransactionRequest to request a single transaction from
    a delegate by specifying the transaction's hash.

    A delegate receives a TransactionRequest, and creates a TransactionReply including the binary for the specified transaction.

    """

    def validate(self):
        # TODO validate all elemetns of tx_hash are valid 64 char hex
        pass

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return data

    def serialize(self):
        return self._data

    @classmethod
    def create(cls, transaction_hashes: List[str]):
        # TODO implement
        pass

    @property
    def tx_hashes(self) -> List[str]:
        # TODO implement
        pass


class TransactionReply(MessageBase):
    """
    TransactionReply acts as a holder for an individual transaction. They are requested from delegates by Masternodes when
    a Masternode needs to retrieve the block data associated with a BlockContender
    """

    def validate(self):
        self.transactions  # will raise exception if a ContractTransaction cannot be deserialized
        pass

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return data

    def serialize(self):
        return self._data

    @classmethod
    def create(cls, raw_transactions: List[bytes]):
        """
        Creates a TransactionReply object from a list of ContractTransaction binaries.
        :param raw_transactions: A list of ContractTransaction binaries
        :return: A TransactionReply object
        """
        # TODO implement
        pass

    def validate_matches_request(self, request: TransactionRequest) -> bool:
        """
        Validates that this TransactionReply contains transactions, whose hashes match the hashes in TransactionRequest.
        Returns True if this class contains every transaction for each transaction hash in the TransactionRequest
        (none missing, and no extras). Otherwise, returns false
        :param request:
        :return: True if this object has a transaction for every hash in TransactionRequest. False otherwise.
        """
        # TODO implement
        pass

    @lazy_property
    def transactions(self) -> List[ContractTransaction]:
        # TODO implement ... loop over raw transactions and deserialize using ContractTransaction.from_bytes(...)
        pass

