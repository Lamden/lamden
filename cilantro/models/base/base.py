class ModelBase(object):
    """
    ModelBase is the abstract class which defines required methods for any data model that is passed between nodes.
    All models which are transmitted between nodes (i.e. transaction, blocks, routing tables, ect) must subclass this.

    Models are essentially just a wrapper around the underlying data interchange format (Captain Proto or JSON), which
    provide convenient methods for manipulating, reading, and computing functions of the data. They can also provide
    an interface for executing RPC on the data between nodes.
    """

    def serialize(self) -> bytes:
        """
        Serialize the underlying data format into bytes
        :return: Bytes
        """
        raise NotImplementedError

    def validate(self):
        """
        Validates the underlying data, raising an exception if something is wrong
        :return: Void
        :raises: An exception if there if an issues arrises validating the underlying data
        """
        raise NotImplementedError

    @classmethod
    def from_bytes(cls, data: bytes, validate=True):
        """
        Deserializes binary data and uses it as the underlying data for the newly instantiated ModelBase class
        If validate=True, then this method also calls validate on the newly created Model object.
        :param data: The binary data of the underlying data interchange format
        :param validate: If true, this method will also validate the data before returning the model object
        :return: An instance of ModelBase
        """
        raise NotImplementedError

    @classmethod
    def from_data(cls, data: object, validate=True):
        """
        Creates a ModelBase and directly for the deserialized data.
        If validate=True, then this method also calls validate on the newly created Model object.
        :param data: The object to use as the underlying data format (i.e. Capnp Struct, JSON dict)
        :param validate: If true, this method will also validate the data before returning the model object
        :return: An instance of ModelBase
        """
        raise NotImplementedError
