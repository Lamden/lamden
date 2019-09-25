import time

from cilantro_ee.core.messages.message_type import MessageType
from cilantro_ee.core.messages.capnp_impl.capnp_impl import CapnpImpl


class Message:
    _msg_impl = CapnpImpl()  # currently only capnp implementation is available

    # returns msg_type, encoded_msg
    @classmethod
    def get_message(cls, msg_type: MessageType, **kwargs):
        return cls._msg_impl.get_message(msg_type=msg_type, **kwargs)

    # returns msg_type, encoded_msg_packed
    @classmethod
    def get_message_packed(cls, msg_type: MessageType, **kwargs):
        return cls._msg_impl.get_message_packed(msg_type=msg_type, **kwargs)

    # returns encoded_msg_type, signed_encoded_msg_packed
    @classmethod
    def get_signed_message_packed(cls, signee: bytes, sign: callable, msg_type: MessageType, **kwargs):
        return cls._msg_impl.get_signed_message_packed(
            signee=signee, sign=sign,
            msg_type=msg_type, **kwargs)

    # returns msg_type, encoded_msg, sender, timestamp, is_verified
    @classmethod
    def unpack_message(cls, msg_type: bytes, message: bytes,
                       sender: bytes = None, timestamp: float = time.time(),
                       is_verify: bool = True):
        return cls._msg_impl.unpack_message(
            msg_type=msg_type, message=message,
            sender=sender, timestamp=timestamp,
            is_verify=is_verify)