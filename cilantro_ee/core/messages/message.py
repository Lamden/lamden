from cilantro_ee.core.messages.message_type import MessageType
from cilantro_ee.core.messages.capnp_impl.capnp_impl import CapnpImpl


class Message:

    _msg_impl = CapnpImpl()   # currently only capnp implementation is available

    # returns msg_type, encoded_msg
    @classmethod
    def get_message(cls, msg_type, **kwargs):
        return cls._msg_impl.get_message(msg_type=msg_type, **kwargs)

    # returns msg_type, encoded_msg_packed
    @classmethod
    def get_message_packed(cls, msg_type, **kwargs):
        return cls._msg_impl.get_message_packed(msg_type=msg_type, **kwargs)

    # returns encoded_msg_type, signed_encoded_msg_packed
    @classmethod
    def get_signed_message_packed(cls, msg_type, **kwargs):
        return cls._msg_impl.get_signed_message_packed(msg_type=msg_type, **kwargs)

    # returns msg_type, encoded_msg, sender, timestamp
    @classmethod
    def unpack_message(cls, msg_type, **kwargs):
        return cls._msg_impl.get_signed_message_packed(msg_type=msg_type, **kwargs)
