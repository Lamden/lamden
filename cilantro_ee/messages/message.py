import time
from cilantro_ee.messages.message_type import MessageType
from cilantro_ee.messages.capnp_impl.capnp_impl import CapnpImpl
from cilantro_ee.crypto.wallet import Wallet
import struct


class Message:
    _msg_impl = CapnpImpl()   # currently only capnp implementation is available


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
    def get_signed_message_packed(cls, wallet: Wallet, msg_type: MessageType, **kwargs):
        return cls._msg_impl.get_signed_message_packed(
                                  wallet=wallet,
                                  msg_type=msg_type,**kwargs)

    # returns encoded_msg_type, signed_encoded_msg_packed
    @classmethod
    def get_message_signed_internal(cls, signee: bytes, sign: callable, msg_type: bytes, msg: bytes):
        return cls._msg_impl._get_message_signed(
                                  signee=signee, sign=sign,
                                  msg_type=msg_type, msg=msg)

    # returns encoded_msg

    @classmethod
    def unpack_message_internal(cls, msg_type: MessageType, message: bytes):
        _, msg, _, _, _ = cls._msg_impl._unpack_message(
            msg_type=msg_type, message=message,
            is_verify=False)

        return msg

    # returns msg_type, encoded_msg, sender, timestamp, is_verified
    @classmethod
    def unpack_message(cls, msg_type: bytes, message: bytes,
                       sender: bytes = None, timestamp: float = time.time(),
                       is_verify: bool = True):
        return cls._msg_impl.unpack_message(
                                 msg_type=msg_type, message=message,
                                 sender=sender, timestamp=timestamp,
                                 is_verify=is_verify)

    @classmethod
    def unpack_message_2(cls, message: bytes):
        msg_type = struct.pack('B', message[0])
        msg_blob = message[1:]

        return cls._msg_impl.unpack_message(msg_type=msg_type, message=msg_blob)

    @classmethod
    def get_signed_message_packed_2(cls, wallet: Wallet, msg_type: MessageType, **kwargs):
        t, m = cls._msg_impl.get_signed_message_packed(
            wallet=wallet,
            msg_type=msg_type, **kwargs)

        return t + m

    @classmethod
    def get_message_packed_2(cls, msg_type: MessageType, **kwargs):
        t, m = cls._msg_impl.get_message_packed(msg_type=msg_type, **kwargs)

        return t + m
