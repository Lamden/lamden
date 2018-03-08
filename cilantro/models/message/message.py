from typing import Type
from cilantro.models import ModelBase
import capnp
import message_capnp

# TODO -- move these constants somewhere else
from cilantro.models import MerkleTree
from cilantro.models import StandardTransaction
MODEL_TYPES = {MerkleTree.name: {'cls': MerkleTree, 'id': 0},
               StandardTransaction.name: {'cls': StandardTransaction, 'id': 1}}


class Message(ModelBase):

    def validate(self):
        """
        Validates the underlying data, raising an exception if something is wrong
        :return: Void
        :raises: An exception if there if an issues arrises validating the underlying data
        """
        # print("Message Validating...")
        # TODO -- implement

    @property
    def type(self):
        return self._data.type

    @classmethod
    def deserialize_struct(cls, data: bytes):
        """
        Deserializes the captain proto structure and returns it. This method is only intended to be used internally
        (as it returns a Capnp struct and not a ModelBase instance).
        To build a ModelBase object from bytes use ModelBase.from_bytes(...)
        :param data: The encoded captain proto structure
        :return: A captain proto struct reader
        """
        return message_capnp.Message.from_bytes_packed(data)

    @classmethod
    def create(cls, model: Type[ModelBase], data: bytes):
        """
        Creates a new message of the specified type, with a payload binary equal to bytes
        :param model: The class of ModelBase which the data payload will store
        :param data: The binary data for the ModelBase instance contained in this message
        :return: An instance of Message
        """
        struct = message_capnp.Message.new_message()
        struct.type = MODEL_TYPES[model.name]['id']
        struct.payload = data
        msg = cls.from_data(struct)

        return msg
