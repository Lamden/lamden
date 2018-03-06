from cilantro import Constants
from cilantro.models.base import ModelBase
from cilantro.models.utils import validate_hex
import capnp
# import transaction_capnp


class TransactionBase(ModelBase):
    """
    This class encapsulates the abstract data model for Transactions.
    """

    def __init__(self, data):
        self._data = data
        self.pow = Constants.Protocol.Proofs
        self.wallet = Constants.Protocol.Wallets

    def serialize(self) -> bytes:
        """
        Serialize the underlying data format into bytes
        :return: Bytes
        """
        if not self._data:
            raise Exception("internal attribute _data not set.")
        return self._data.as_builder().to_bytes_packed()

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
        payload_binary = self._data.payload.as_builder().copy().to_bytes()
        if not self.pow.check(payload_binary, self._data.metadata.proof.decode()):
            raise Exception("Invalid proof of work for tx: {}".format(self._data))

    def validate_signature(self):
        """
        Checks the signature on the transaction payload, raising an exception if it is not signed by the sender.
        If the signature is valid, this method returns nothing.
        :raises: An exception if the signature is invalid
        """
        payload_binary = self._data.payload.as_builder().copy().to_bytes()
        if not self.wallet.verify(self.sender, payload_binary, self.signature):
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

    @classmethod
    def deserialize_struct(cls, data: bytes):
        """
        Deserializes the captain proto structure and returns it. This method should be implemented by all subclasses
        :param data: The encoded captain proto structure
        :return: A captain proto struct reader
        """
        raise NotImplementedError

    @classmethod
    def from_bytes(cls, data: bytes, validate=True):
        """
        Deserializes binary data and uses it as the underlying data for the newly instantiated Transaction class
        If validate=True, then this method also calls validate on the newly created Transaction object.
        :param data: The binary data of the underlying data interchange format
        :param validate: If true, this method will also validate the data before returning the model object
        :return: An instance of Transaction
        """
        model = cls(cls.deserialize_struct(data))
        if validate:
            model.validate()
        return model

    @classmethod
    def from_data(cls, data: object, validate=True):
        """
        Creates a ModelBase and directly for the deserialized data.
        If validate=True, then this method also calls validate on the newly created Transaction object.
        :param data: The object to use as the underlying data format (i.e. Capnp Struct, JSON dict)
        :param validate: If true, this method will also validate the data before returning the model object
        :return: An instance of Transaction
        """
        # Cast data to a struct reader (not builder) if it isn't already
        if hasattr(data, 'as_reader'):
            data = data.as_reader()

        model = cls(data)
        if validate:
            model.validate()
        return model

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



