from cilantro import Constants
from cilantro.messages.base.base import MessageBase
from cilantro.messages.utils import validate_hex
from cilantro.db.delegate import contract
from cilantro.utils import lazy_property
import capnp


class TransactionBase(MessageBase):
    """
    This class encapsulates the abstract data model for Transactions.
    """

    def __init__(self, data):
        super().__init__(data)
        self.pow = Constants.Protocol.Proofs
        self.wallet = Constants.Protocol.Wallets

    def interpret(self, *args, **kwargs):
        """
        Interprets the transaction and returns the SQLAlchemy queries associated with the transaction's changes
        :return: SQLAlchemy query objects
        """
        assert hasattr(type(self), 'contract'), "Transaction type {} has no contract defined".format(type(self))
        return contract(type(self))(type(self).contract)(self, *args, **kwargs)

    def validate(self):
        """
        Validates the underlying data, raising an exception if something is wrong
        :return: Void
        :raises: An exception if there if an issues arrises validating the underlying data
        """
        if not self._data:
            raise Exception("internal attribute _data not set.")

        self.validate_metadata()
        self.validate_payload()
        self.validate_pow()
        self.validate_signature()

    def validate_pow(self):
        """
        Checks the POW on the transaction payload, raising an exception if it does not have sufficient leading 0s.
        If the POW is valid, this method returns nothing.
        :raises: An exception if the POW is not valid.
        """
        if not self.pow.check(self._payload_binary, self._data.metadata.proof.decode()):
            raise Exception("Invalid proof of work for tx: {}".format(self._data))

    def validate_signature(self):
        """
        Checks the signature on the transaction payload, raising an exception if it is not signed by the sender.
        If the signature is valid, this method returns nothing.
        :raises: An exception if the signature is invalid
        """
        if not self.wallet.verify(self.sender, self._payload_binary, self.signature):
            raise Exception("Invalid signature for tx: {}".format(self._data))

    def validate_metadata(self):
        """
        Checks the fields in the metadata, namely proof and signature.
        :raises: An exception if either the proof or signature are not valid hexadecimal of the appropriate length
        """
        validate_hex(self.proof, 32, 'proof')
        validate_hex(self.signature, 128, 'signature')

    def validate_payload(self):
        """
        Checks if the fields on the transaction payload and raises an exception if anything is invalid.
        If all fields are valid, this method returns nothing. This method should be implemented by subclasses
        :raises: An exception if the fields are somehow invalid
        """
        raise NotImplementedError

    @lazy_property
    def _payload_binary(self):
        if hasattr(self._data.payload, 'copy'):
            return self._data.payload.copy().to_bytes()
        else:
            return self._data.payload.as_builder().copy().to_bytes()

    @property
    def proof(self):
        return self._data.metadata.proof.decode()

    @property
    def signature(self):
        return self._data.metadata.signature.decode()

    @property
    def timestamp(self):
        return self._data.metadata.timestamp.decode()

    @property
    def sender(self):
        return self._data.payload.sender.decode()



