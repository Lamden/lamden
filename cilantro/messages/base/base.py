"""
Messages encapsulate data that is sent between nodes.
"""

class MessageMeta(type):
    def __new__(cls, clsname, bases, clsdict):
        #print("MessageMeta NEW called /w class ", clsname)
        clsobj = super().__new__(cls, clsname, bases, clsdict)
        if not hasattr(clsobj, 'registry'):
            print("Creating Registry")
            clsobj.registry = {}
        #print("Adding to registry: ", clsobj)

        # Define an "undirected" mapping between classes and their enum vals
        l = len(clsobj.registry) // 2
        clsobj.registry[clsobj] = l
        clsobj.registry[l] = clsobj

        return clsobj


class MessageBase(metaclass=MessageMeta):
    """
    MessageBase is the abstract class which defines required methods for any data model that is passed between nodes.
    All messages which are transmitted between nodes (i.e. transaction, blocks, routing tables, ect) must subclass this.

    Message are essentially just a wrapper around the underlying data interchange format (Captain Proto or JSON), which
    provide convenient methods for manipulating, reading, and computing functions of the data. This must implement
    _deserialize_data(..), as well as serialize(..) if the underlying data (_data) is not capnp.

    Messages can also provide an interface for executing RPC on the data between nodes.
    """

    def __init__(self, data):
        self._data = data

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
        raise NotImplementedError

    @classmethod
    def _deserialize_data(cls, data: bytes):
        """
        Deserializes the captain proto structure and returns it. This method should be implemented by all subclasses,
        and is only intended to be used internally (as it returns a Capnp struct and not a MessageBase instance).
        To build a MessageBase object from bytes use MessageBase.from_bytes(...)
        :param data: The encoded captain proto structure
        :return: A captain proto struct reader (or whatever underlying deserialzed data representation the
                 message uses, i.e. a dict if JSON)
        """
        raise NotImplementedError

    @classmethod
    def from_bytes(cls, data: bytes, validate=True):
        """
        Deserializes binary data and uses it as the underlying data for the newly instantiated Message class
        If validate=True, then this method also calls validate on the newly created Message object.
        :param data: The binary data of the underlying data interchange format
        :param validate: If true, this method will also validate the data before returning the message object
        :return: An instance of MessageBase
        """
        model = cls.from_data(cls._deserialize_data(data), validate=False)
        if validate:
            model.validate()
        return model

    @classmethod
    def from_data(cls, data: object, validate=True):
        """
        Creates a MessageBase directly from the python data object (dict, capnp struct, str, ect).
        If validate=True, then this method also calls validate on the newly created Message object.
        :param data: The object to use as the underlying data format (i.e. Capnp Struct, JSON dict)
        :param validate: If true, this method will also validate the data before returning the message object
        :return: An instance of MessageBase
        """
        # Cast data to a struct reader (not builder) if it isn't already
        if hasattr(data, 'as_reader'):
            data = data.as_reader()

        model = cls(data)
        if validate:
            model.validate()
        return model

    def __repr__(self):
        return str(self._data)
