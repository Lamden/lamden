from cilantro.utils.lazy_property import lazy_func
import capnp
import hashlib

"""
Messages encapsulate data that is sent between nodes.
"""


class MessageBaseMeta(type):
    def __new__(cls, clsname, bases, clsdict):
        clsobj = super().__new__(cls, clsname, bases, clsdict)
        if not hasattr(clsobj, 'registry'):
            clsobj.registry = {}

        # Define an "undirected" mapping between classes and their enum vals
        m = hashlib.md5()
        m.update(clsobj.__name__.encode())
        l = int(m.digest().hex(),16) % pow(2, 16)
        assert clsobj.registry.get(l) == None, 'Registry enum collision of message class {}!'.format(clsobj.__name__)

        clsobj.registry[clsobj] = l
        clsobj.registry[l] = clsobj

        return clsobj


class MessageBase(metaclass=MessageBaseMeta):
    """
    MessageBase is the abstract class which defines required methods for any data model that is passed between nodes.
    All messages which are transmitted between nodes (i.e. transaction, blocks, routing tables, ect) must subclass this.

    Messages are essentially just a wrapper around the underlying data interchange format (Captain Proto or JSON), which
    provide convenient methods for manipulating, reading, and computing functions of the data. All subclasses must implement
    _deserialize_data(..) and validate(). If the underlying data (_data) is not capnp, they must
    also implement serialize()

    Messages can also provide an interface for executing RPC on the data between nodes.
    """

    def __init__(self, data):
        self._data = data

    @lazy_func
    def serialize(self) -> bytes:
        """
        Serialize the underlying data format into bytes
        :return: Bytes
        """
        assert self._data, "Serialization error: internal _data not set"
        assert type(self._data) in (capnp.lib.capnp._DynamicStructBuilder, capnp.lib.capnp._DynamicStructReader), \
            "Serialization error: class of self._data is not a capnp _DynamicStructReader or _DynamicStructBuilder"

        # Cast to struct builder if needed (reader does not have to_bytes_packed() method)
        if type(self._data) is capnp.lib.capnp._DynamicStructReader:
            return self._data.as_builder().to_bytes_packed()
        else:
            return self._data.to_bytes_packed()

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
        model = cls.from_data(cls._deserialize_data(data), validate=validate)
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
        model = cls(data)
        if validate:
            model.validate()

        return model

    def __eq__(self, other):
        assert type(self) is type(other), "Cannot compare messages of seperate classes {} and {}. " \
                                          "Override __eq__ to support this behavior".format(type(self), type(other))
        assert self._data, "._data is None set for LHS"
        assert other._data, "._data is None for RHS"

        if hasattr(self._data, 'to_dict') and hasattr(other._data, 'to_dict'):
            return self._data.to_dict() == other._data.to_dict()
        else:

            raise NotImplementedError("Default __eq__ is only implement for messages that use capnp (no to_dict method "
                                      "found on object type {} or {}".format(type(self), type(other)))

    def __repr__(self):
        return str(self._data)
