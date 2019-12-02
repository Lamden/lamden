import os
import time
import capnp

from cilantro_ee.core.messages.message_type import MessageType
import struct
from cilantro_ee.core.crypto.wallet import _sign
from cilantro_ee.core.crypto.wallet import Wallet
from cilantro_ee.core.messages.message_type import MessageType


def pack(i: int):
    return struct.pack('B', i)


def unpack(b: bytes):
    return struct.unpack('B', b)[0]


class CapnpImpl:
    def __init__(self):
        from cilantro_ee.core.messages.capnp_impl import capnp_struct as schemas

        self.blockdata_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/blockdata.capnp')
        self.notification_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/notification.capnp')
        self.signed_message_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/signed_message.capnp')
        self.subblock_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/subblock.capnp')
        self.transaction_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/transaction.capnp')
        self.signals_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/signals.capnp')

        self.message_capnp = {
            # we don't add this to prevent users directly accessing it
            # MessageType.SIGNED_MESSAGE: get_message,
            MessageType.BLOCK_INDEX_REQUEST: self.blockdata_capnp.BlockIndexRequest,
            MessageType.BLOCK_INDEX_REPLY: self.blockdata_capnp.BlockIndexReply,
            MessageType.BLOCK_DATA_REQUEST: self.blockdata_capnp.BlockDataRequest,
            MessageType.BLOCK_DATA: self.blockdata_capnp.BlockData,               # ?
            MessageType.BLOCK_NOTIFICATION: self.notification_capnp.BlockNotification,  # ?
            MessageType.BURN_INPUT_HASHES: self.notification_capnp.BurnInputHashes,
            MessageType.DISCORD_AND_ALIGN: self.notification_capnp.BurnInputHashes,
            MessageType.SUBBLOCK_CONTENDER: self.subblock_capnp.SubBlockContender,
            MessageType.TRANSACTION_BATCH: self.transaction_capnp.TransactionBatch,
            MessageType.TRANSACTION_DATA: self.transaction_capnp.TransactionData,
            MessageType.TRANSACTION: self.transaction_capnp.Transaction,
            MessageType.MERKLE_PROOF: self.subblock_capnp.MerkleProof,
            MessageType.SUBBLOCK: self.subblock_capnp.SubBlock,
            MessageType.LATEST_BLOCK_HEIGHT_REQUEST: self.signals_capnp.LatestBlockHeightRequest,
            MessageType.LATEST_BLOCK_HEIGHT_REPLY: self.signals_capnp.LatestBlockHeightReply,
            MessageType.LATEST_BLOCK_HASH_REQUEST: self.signals_capnp.LatestBlockHashRequest,
            MessageType.LATEST_BLOCK_HASH_REPLY: self.signals_capnp.LatestBlockHashReply,
            MessageType.IP_FOR_VK_REQUEST: self.signals_capnp.IPForVKRequest,
            MessageType.IP_FOR_VK_REPLY: self.signals_capnp.IPForVKReply,
            MessageType.BAD_REQUEST: self.signals_capnp.BadRequest,
            MessageType.ACKNOWLEDGED: self.signals_capnp.Acknowledged,
        }

    def get_message(self, msg_type: MessageType, **kwargs):
        mtype_bytes = pack(int(msg_type))
        if msg_type in self.message_capnp:
            return mtype_bytes, self.message_capnp[msg_type].new_message(**kwargs)
        return mtype_bytes, ''

    def get_message_packed(self, msg_type: MessageType, **kwargs):
        mtype_bytes = pack(int(msg_type))
        if msg_type in self.message_capnp:
            return mtype_bytes, self.message_capnp[msg_type].new_message(**kwargs).to_bytes_packed()
        return mtype_bytes, b''

    # def get_signed_message(self, signee: bytes, sign: callable, msg_type: MessageType, **kwargs):
        # return None, None     # prevent using this directly until we know use cases

    def get_signed_message_packed(self, wallet: Wallet, msg_type: MessageType, **kwargs):
        msg_type, msg = self.get_message_packed(msg_type, **kwargs)
        sig = wallet.sign(msg)

        signed_msg = self.signed_message_capnp.SignedMessage.new_message(
            msgType=msg_type,
            message=msg,
            signature=sig,
            signee=wallet.vk.encode(),
            timestamp=time.time()
        )

        return pack(int(MessageType.SIGNED_MESSAGE)), signed_msg.to_bytes_packed()

    def _get_message_signed(self, signee: bytes, sign: callable, msg_type: bytes, msg: bytes):
        sig = sign(msg)
        signed_msg = self.signed_message_capnp.SignedMessage.new_message(msgType=msg_type,
                            message=msg, signature=sig, signee=signee, timestamp=time.time())
        return pack(int(MessageType.SIGNED_MESSAGE)), signed_msg.to_bytes_packed()

    def unpack_message(self, msg_type: bytes, message: bytes,
                       sender: bytes = None, timestamp: float = time.time(),
                       is_verify: bool = True):

        msg_type = unpack(msg_type)

        return self._unpack_message(MessageType(msg_type), message, sender, timestamp, is_verify)

    def _unpack_message(self, msg_type: MessageType,  message: bytes,
                        sender: bytes = None, timestamp: float = time.time(),
                        is_verify: bool = True):

        if msg_type == MessageType.SIGNED_MESSAGE:
            return self._unpack_signed_message(message, is_verify)

        if msg_type in self.message_capnp:
            return msg_type, self.message_capnp[msg_type].from_bytes_packed(message), sender, timestamp, True

        return msg_type, None, sender, timestamp, True

    def _unpack_signed_message(self, message: bytes, is_verify: bool):
        signed_msg = self.signed_message_capnp.SignedMessage.from_bytes_packed(message)
        # if is_verify and not verified:
            # return signed_msg.msgType, None, signed_msg.signee, signed_msg.timestamp, False
        if is_verify:
            pass        # todo verify

        return self.unpack_message(msg_type=signed_msg.msgType,
                                   message=signed_msg.message,
                                   sender=signed_msg.signee,
                                   timestamp=signed_msg.timestamp)
