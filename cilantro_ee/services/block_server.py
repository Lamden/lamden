from cilantro_ee.core.sockets.services import AsyncInbox

from cilantro_ee.services.storage.master import CilantroStorageDriver
from cilantro_ee.core.top import TopBlockManager
from cilantro_ee.core.messages.message import Message
from cilantro_ee.core.messages.message_type import MessageType
import os
import capnp
from cilantro_ee.core.messages.capnp_impl import capnp_struct as schemas
import json
import struct
import time

blockdata_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/blockdata.capnp')
subblock_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/subblock.capnp')


# Provide a block blocks to enable data and index requests
# Otherwise, this will just return latest num and hash, which both delegates and masters can do
class BlockServer(AsyncInbox):
    def __init__(self, socket_id, wallet, ctx, linger, poll_timeout, driver: CilantroStorageDriver=None, top=TopBlockManager()):
        self.driver = driver
        self.top = top
        super().__init__(socket_id=socket_id,
                         wallet=wallet,
                         ctx=ctx,
                         linger=linger,
                         poll_timeout=poll_timeout)

    async def handle_msg(self, _id, msg):
        msg_type, msg, sender, timestamp, is_verified = Message.unpack_message_2(message=msg)

        if msg_type == MessageType.BLOCK_DATA_REQUEST and self.driver is not None:

            block_dict = self.driver.get_block(msg.blockNum)

            if block_dict is not None:
                block_hash = block_dict.get('blockHash')
                block_num = block_dict.get('blockNum')
                prev_hash = block_dict.get('prevBlockHash')
                subblocks = block_dict.get('subBlocks')
                owners = block_dict.get('blockOwners')

                reply = Message.get_signed_message_packed_2(wallet=self.wallet,
                                                            msg_type=MessageType.BLOCK_DATA,
                                                            blockHash=block_hash,
                                                            blockNum=block_num,
                                                            blockOwners=[owner for owner in owners],
                                                            prevBlockHash=prev_hash,
                                                            subBlocks=[subblock_capnp.SubBlock.new_message(**sb) for sb in subblocks],
                                                            )

                await self.return_msg(_id, reply)
            else:
                reply = Message.get_signed_message_packed_2(wallet=self.wallet,
                                                            msg_type=MessageType.BAD_REQUEST,
                                                            timestamp=int(time.time()))
                await self.return_msg(_id, reply)

        elif msg_type == MessageType.BLOCK_INDEX_REQUEST and self.driver is not None:
            await self.return_msg(_id, b'howdy')

        elif msg_type == MessageType.LATEST_BLOCK_HEIGHT_REQUEST:
            reply = Message.get_signed_message_packed_2(wallet=self.wallet,
                                                        msg_type=MessageType.LATEST_BLOCK_HEIGHT_REPLY,
                                                        blockHeight=self.top.get_latest_block_number())

            await self.return_msg(_id, reply)

        elif msg_type == MessageType.LATEST_BLOCK_HASH_REQUEST:
            reply = Message.get_signed_message_packed_2(wallet=self.wallet,
                                                        msg_type=MessageType.LATEST_BLOCK_HASH_REPLY,
                                                        blockHash=self.top.get_latest_block_hash())

            await self.return_msg(_id, reply)
        else:
            reply = Message.get_signed_message_packed_2(wallet=self.wallet,
                                                        msg_type=MessageType.BAD_REQUEST,
                                                        timestamp=int(time.time()))
            await self.return_msg(_id, reply)
