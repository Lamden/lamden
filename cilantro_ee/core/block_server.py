from cilantro_ee.sockets.services import AsyncInbox

from cilantro_ee.storage import CilantroStorageDriver, BlockchainDriver
from cilantro_ee.messages.message import Message
from cilantro_ee.messages.message_type import MessageType
from cilantro_ee.networking.parameters import ServiceType, NetworkParameters
import os
import capnp
from cilantro_ee.messages.capnp_impl import capnp_struct as schemas
import time
import asyncio
import zmq, zmq.asyncio

subblock_capnp = capnp.load(os.path.dirname(schemas.__file__) + '/subblock.capnp')


# Provide a block blocks to enable data and index requests
# Otherwise, this will just return latest num and hash, which both delegates and masters can do

class BlockServer(AsyncInbox):
    def __init__(self, wallet, socket_base, ctx=None, network_parameters=NetworkParameters(), linger=500,
                 poll_timeout=200, blocks: CilantroStorageDriver=None, driver=BlockchainDriver()):

        self.wallet = wallet
        self.ctx = ctx or zmq.asyncio.Context()
        self.address = network_parameters.resolve(socket_base, ServiceType.BLOCK_SERVER, bind=True)

        super().__init__(socket_id=self.address,
                         wallet=self.wallet,
                         ctx=self.ctx,
                         linger=linger,
                         poll_timeout=poll_timeout)

        self.blocks = blocks or CilantroStorageDriver(key=self.wallet.signing_key())
        self.driver = driver

    def sync_serve(self):
        asyncio.get_event_loop().run_until_complete(
            asyncio.ensure_future(self.serve())
        )

    async def handle_msg(self, _id, msg):
        msg_type, msg, sender, timestamp, is_verified = Message.unpack_message_2(message=msg)

        if msg_type == MessageType.BLOCK_DATA_REQUEST and self.blocks is not None:

            block_dict = self.blocks.get_block(msg.blockNum)

            if block_dict is not None:
                block_hash = block_dict.get('blockHash')
                block_num = block_dict.get('blockNum')
                prev_hash = block_dict.get('prevBlockHash')
                subblocks = block_dict.get('subBlocks')
                owners = block_dict.get('blockOwners')

                reply = Message.get_signed_message_packed_2(
                    wallet=self.wallet,
                    msg_type=MessageType.BLOCK_DATA,
                    blockHash=block_hash,
                    blockNum=block_num,
                    blockOwners=[owner for owner in owners],
                    prevBlockHash=prev_hash,
                    subBlocks=[subblock_capnp.SubBlock.new_message(**sb) for sb in subblocks],
                )

                await self.return_msg(_id, reply)
            else:
                reply = Message.get_signed_message_packed_2(
                    wallet=self.wallet,
                    msg_type=MessageType.BAD_REQUEST,
                    timestamp=int(time.time())
                )

                await self.return_msg(_id, reply)

        elif msg_type == MessageType.BLOCK_INDEX_REQUEST and self.blocks is not None:
            await self.return_msg(_id, b'howdy')

        elif msg_type == MessageType.LATEST_BLOCK_HEIGHT_REQUEST:
            reply = Message.get_signed_message_packed_2(
                wallet=self.wallet,
                msg_type=MessageType.LATEST_BLOCK_HEIGHT_REPLY,
                blockHeight=self.driver.get_latest_block_num()
            )

            await self.return_msg(_id, reply)

        elif msg_type == MessageType.LATEST_BLOCK_HASH_REQUEST:
            reply = Message.get_signed_message_packed_2(
                wallet=self.wallet,
                msg_type=MessageType.LATEST_BLOCK_HASH_REPLY,
                blockHash=self.driver.get_latest_block_hash()
            )

            await self.return_msg(_id, reply)
        else:
            reply = Message.get_signed_message_packed_2(
                wallet=self.wallet,
                msg_type=MessageType.BAD_REQUEST,
                timestamp=int(time.time())
            )

            await self.return_msg(_id, reply)
