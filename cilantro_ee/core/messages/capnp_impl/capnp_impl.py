import os
import time
import capnp

from cilantro_ee.core.messages.message_type import MessageType


class CapnpImpl:
    def __init__(self):
        from cilantro_ee.core.messages.capnp_impl import capnp_struct as schemas

        self.blockdata_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/blockdata.capnp')
        self.notification_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/notification.capnp')
        self.signed_message_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/signed_message.capnp')
        self.subblock_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/subblock.capnp')
        self.transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')

        self.message_capnp = {
            # we don't add this to prevent users directly accessing it
            # MessageType.SIGNED_MESSAGE: get_message,
            MessageType.BLOCK_INDEX_REQUEST: self.blockdata_capnp.BlockIndexRequest,
            # MessageType.BLOCK_INDEX_REPLY: self.blockdata_capnp.BlockIndexReply,        # ?
            MessageType.BLOCK_DATA_REQUEST: self.blockdata_capnp.BlockDataRequest,
            MessageType.BLOCK_DATA_REPLY: self.blockdata_capnp.BlockData,               # ?
            MessageType.BLOCK_NOTIFICATION: self.notification_capnp.BlockNotification,  # ?
            MessageType.BURN_INPUT_HASHES: self.notification_capnp.BurnInputHashes,
            MessageType.SUBBLOCK_CONTENDER: self.subblock_capnp.SubBlockContender,
            MessageType.TRANSACTION_BATCH: self.transaction_capnp.TransactionBatch,
        }


    def get_message(self, msg_type: MessageType, **kwargs):
        if msg_type in self.message_capnp:
            return msg_type, self.message_capnp[msg_type].new_message(**kwargs)
        return msg_type, ''

    def get_message_packed(self, msg_type: MessageType, **kwargs):
        if msg_type in self.message_capnp:
            return msg_type, self.message_capnp[msg_type].new_message(**kwargs).to_bytes_packed()
        return msg_type, b''

    # def get_signed_message(self, signee: bytes, sign: callable, msg_type: MessageType, **kwargs):
        # return None, None     # prevent using this directly until we know use cases
        
    def get_signed_message_packed(self, signee: bytes, sign: callable, msg_type: MessageType, **kwargs):
        msg_type, msg = self.get_message_packed(msg_type, kwargs)
        sig = sign(msg)
        signed_msg = signed_message_capnp.SignedMessage.new_message(msgType=msg_type,
                            message= msg, signature=sig, signee=signee, timestamp=time.time())
        return MessageType.SIGNED_MESSAGE, signed_msg

    def unpack_message(self, msg_type: MessageType, message: bytes,
                       sender: bytes = None, timestamp: float = time.time(),
                       is_verify: bool = True):
        if msg_type == MessageType.SIGNED_MESSAGE:
            return self._unpack_signed_message(message, is_verify)
        if msg_type in self.message_capnp:
            return msg_type, self.message_capnp[msg_type].from_bytes_packed(msg), sender, timestamp
        return None, None, sender, timestamp

    def _unpack_signed_message(self, message: bytes, is_verify: bool):
        signed_msg = signed_message_capnp.SignedMessage.from_bytes_packed(message)
        if is_verify:
            pass        # todo verify
        # todo - may need to return timestamp too ??
        return self.unpack_message(msg_type=signed_msg.msgType, message=signed_msg.message,
                                   sender=signed_msg.signee, timestamp=signed_msg.timestamp)
