from cilantro.messages.base.base import MessageBase
from cilantro.messages.transaction.contract import ContractTransaction
from cilantro.utils import lazy_property, Hasher
from cilantro.messages.utils import validate_hex
from typing import List
from cilantro.logger import get_logger

import capnp
import blockdata_capnp

log = get_logger(__name__)

# TODO switch this class to use capnp, and also
class TransactionRequest(MessageBase):
    """
    BlockData requests/replies are used to transfer transactions from a block between masternode/delegate.

    When Masternode is attempting to publish a new block, it creates a TransactionRequest to request a single transaction from
    a delegate by specifying the transaction's hash.

    A delegate receives a TransactionRequest, and creates a TransactionReply including the binary for the specified transaction.

    """

    def validate(self):
        for hash in self._data.transactions:
            validate_hex(hash, 64)
        return True

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return blockdata_capnp.TransactionRequest.from_bytes_packed(data)

    @classmethod
    def create(cls, transaction_hashes: List[str]):
        struct = blockdata_capnp.TransactionRequest.new_message()
        struct.init('transactions', len(transaction_hashes))
        struct.transactions = transaction_hashes
        return cls.from_data(struct)

    @property
    def tx_hashes(self) -> List[str]:
        return [hash.decode() for hash in self._data.transactions]


class TransactionReply(MessageBase):
    """
    TransactionReply acts as a holder for an individual transaction. They are requested from TESTNET_DELEGATES by Masternodes when
    a Masternode needs to retrieve the block data associated with a BlockContender
    """

    def validate(self):
        self.transactions  # will raise exception if a ContractTransaction cannot be deserialized

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return blockdata_capnp.TransactionReply.from_bytes_packed(data)

    @classmethod
    def create(cls, raw_transactions: List[bytes]):
        """
        Creates a TransactionReply object from a list of ContractTransaction binaries.
        :param raw_transactions: A list of ContractTransaction binaries
        :return: A TransactionReply object
        """
        struct = blockdata_capnp.TransactionReply.new_message()
        struct.init('transactions', len(raw_transactions))
        struct.transactions = raw_transactions
        return cls.from_data(struct)

    def validate_matches_request(self, request: TransactionRequest) -> bool:
        """
        Validates that this TransactionReply contains transactions, whose hashes match the hashes in TransactionRequest.
        Returns True if this class contains every transaction for each transaction hash in the TransactionRequest
        (none missing, and no extras). Otherwise, returns false
        :param request:
        :return: True if this object has a transaction for every hash in TransactionRequest. False otherwise.
        """
        if len(self._data.transactions) != len(request._data.transactions):
            return False
        req_hashes = request.tx_hashes
        for i, self_t in enumerate(self._data.transactions):
            request_t = req_hashes[i]
            if Hasher.hash(self_t) != request_t:
                return False
        return True

    @property
    def raw_transactions(self) -> List[bytes]:
        return [t for t in self._data.transactions]

    @lazy_property
    def transactions(self) -> List[ContractTransaction]:
        return [ContractTransaction.from_bytes(t) for t in self.raw_transactions]
