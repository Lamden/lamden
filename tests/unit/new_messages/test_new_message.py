from unittest import TestCase
from cilantro_ee.protocol.wallet import Wallet
from cilantro_ee.protocol.pow import SHA3POWBytes
from cilantro_ee.core.messages.message import Message
from cilantro_ee.core.messages.capnp_impl import capnp_struct as schemas
from cilantro_ee.core.messages.message_type import MessageType
from cilantro_ee.core.messages.capnp_impl.capnp_impl import CapnpImpl

import os
import capnp

blockdata_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/blockdata.capnp')


class TestMessages(TestCase):
    def test_message_new_api(self):
        capnp_impl = CapnpImpl()
        message = blockdata_capnp.BlockDataRequest.new_message(blockNum=123)
        msgType, same_message = capnp_impl.get_message(msg_type=MessageType.BLOCK_DATA_REQUEST, blockNum=123)

        # mtype1, msg1 = Message.get_message(msg_type=MessageType.BLOCK_DATA_REQUEST, blockNum=123)
        mtype1, msg1 = Message.get_message(MessageType.BLOCK_DATA_REQUEST, blockNum=123)
       
        self.assertEqual(msgType, mtype1)
        self.assertEqual(message.blockNum, msg1.blockNum)

        self.assertEqual(msgType, MessageType.BLOCK_DATA_REQUEST)
        self.assertEqual(message.blockNum, same_message.blockNum)

    def test_unpack_returns_equal_capnp_struct(self):
        capnp_impl = CapnpImpl()
        msgType, message = capnp_impl.get_message(msg_type=MessageType.BLOCK_DATA_REQUEST, blockNum=237)
        msgType2, packed = capnp_impl.get_message_packed(msg_type=MessageType.BLOCK_DATA_REQUEST, blockNum=237)

        unpacked_message = blockdata_capnp.BlockDataRequest.from_bytes_packed(packed)

        self.assertEqual(msgType, msgType2)
        self.assertEqual(message.blockNum, unpacked_message.blockNum)

    def test_signal(self):
        capnp_impl = CapnpImpl()
        _, message = capnp_impl.get_message(msg_type=MessageType.READY)
        print("rpc msg {}".format(message))
        _, message = capnp_impl.get_message_packed(msg_type=MessageType.READY)
        print("rpc msg {}".format(message))
