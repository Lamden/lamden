from cilantro_ee.crypto.canonical import verify_block, get_genesis_block
from cilantro_ee.crypto.wallet import Wallet
from cilantro_ee.sockets.services import get
from cilantro_ee.sockets.inbox import AsyncInbox
from cilantro_ee.logger.base import get_logger
from cilantro_ee.storage import CilantroStorageDriver, BlockchainDriver
from cilantro_ee.messages.message import Message
from cilantro_ee.messages.message_type import MessageType
from cilantro_ee.networking.parameters import ServiceType, NetworkParameters, Parameters
import os
import capnp
from cilantro_ee.messages.capnp_impl import capnp_struct as schemas
import time
import zmq
import zmq.asyncio

import random

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
        self.log = get_logger('BlockServer')

    async def handle_msg(self, _id, msg):
        msg_type, msg, sender, timestamp, is_verified = Message.unpack_message_2(message=msg)

        if msg_type == MessageType.BLOCK_DATA_REQUEST and self.blocks is not None:

            self.log.info(f'Sending block data for block #{msg.blockNum}')

            block_dict = self.blocks.get_block(msg.blockNum)

            self.log.info(f'Block data: {block_dict}')

            if block_dict is not None:
                block_hash = block_dict.get('hash')
                block_num = block_dict.get('blockNum')
                prev_hash = block_dict.get('previous')
                subblocks = block_dict.get('subBlocks')
                #owners = block_dict.get('blockOwners')

                try:
                    reply = Message.get_signed_message_packed_2(
                        wallet=self.wallet,
                        msg_type=MessageType.BLOCK_DATA,
                        hash=block_hash,
                        blockNum=block_num,
                        blockOwners=[],
                        previous=prev_hash,
                        subBlocks=[subblock_capnp.SubBlock.new_message(**sb) for sb in subblocks],
                    )
                except Exception as e:
                    self.log.error(str(e))
                    reply = Message.get_signed_message_packed_2(
                        wallet=self.wallet,
                        msg_type=MessageType.BAD_REQUEST,
                        timestamp=int(time.time())
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
            self.log.info(f'Responding to block height request with block #{self.driver.latest_block_num}')
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
                hash=self.driver.get_latest_block_hash()
            )

            await self.return_msg(_id, reply)
        else:
            reply = Message.get_signed_message_packed_2(
                wallet=self.wallet,
                msg_type=MessageType.BAD_REQUEST,
                timestamp=int(time.time())
            )

            await self.return_msg(_id, reply)

class BlockFetcher:
    def __init__(self, wallet: Wallet,
                 ctx: zmq.asyncio.Context,
                 blocks: CilantroStorageDriver=None,
                 state=BlockchainDriver(),
                 parameters: Parameters=None):

        self.parameters = parameters

        self.wallet = wallet
        self.ctx = ctx
        self.blocks = blocks
        self.state = state

        self.blocks_to_process = []

        self.in_catchup = False

        self.log = get_logger('Catchup')

    async def get_latest_block_height(self, socket):
        # Build a signed request
        request = Message.get_signed_message_packed_2(
            wallet=self.wallet,
            msg_type=MessageType.LATEST_BLOCK_HEIGHT_REQUEST,
            timestamp=int(time.time()))

        # Send it to the socket provided and wait for a response
        response = await get(
            socket_id=socket,
            msg=request,
            ctx=self.ctx,
            timeout=1000,
            retries=0,
            dealer=True
        )

        # If it's not none, aka a success, unpack it and return the result
        if response is not None:
            _, unpacked, _, _, _ = Message.unpack_message_2(response)

            return unpacked.blockHeight

    async def get_block_from_master(self, i: int, socket):
        request = Message.get_signed_message_packed_2(
            wallet=self.wallet,
            msg_type=MessageType.BLOCK_DATA_REQUEST,
            blockNum=i
        )

        response = await get(
            socket_id=socket,
            msg=request,
            ctx=self.ctx,
            timeout=1000,
            retries=0,
            dealer=True
        )

        if response is not None:
            msg_type, unpacked, _, _, _ = Message.unpack_message_2(response)

            if msg_type == MessageType.BLOCK_DATA:
                return unpacked

    async def find_valid_block(self, sockets, i, latest_hash):
        if i == 0:
            block = get_genesis_block()
            block['blockNum'] = i
            block['blockOwners'] = []

            return block

        block_found = False
        block = None

        while not block_found:
            # Fire off requests to masternodes on the network
            socket = random.choice(sockets)
            block = await self.get_block_from_master(i, socket)

            self.log.info(f'Got Block {i}')
            self.log.info(f'Previous Hash: {latest_hash}')
            self.log.info(f'Block.Hash: {block.hash}')

            block_found = verify_block(
                subblocks=block.subBlocks,
                previous_hash=latest_hash,
                proposed_hash=block.hash,
                block_num=i
            )

        if block is not None:
            # block_dict = {
            #     'hash': block.hash,
            #     'blockNum': i,
            #     'blockOwners': [],
            #     'previous': latest_hash,
            #     'subBlocks': [s for s in block.subBlocks]
            # }

            return block.to_dict()

    async def fetch_blocks(self, sockets, latest_block_available=0):
        self.log.info('Fetching blocks...')
        latest_block_stored = self.state.get_latest_block_num()
        latest_hash = self.state.get_latest_block_hash()

        self.log.info(f'LBS: {latest_block_stored}, LBA: {latest_block_available}')

        if latest_block_available <= latest_block_stored:
           return

        for i in range(latest_block_stored, latest_block_available + 1):
            await self.find_and_store_block(sockets, i, latest_hash)
            latest_hash = self.state.get_latest_block_hash()

    async def find_and_store_block(self, sockets, block_num, block_hash):
        self.log.info(f'Finding block #{block_num}')

        block_dict = await self.find_valid_block(sockets, block_num, block_hash)

        if self.blocks is not None:
            self.blocks.put(block_dict)

        self.state.update_with_block(block_dict)
        self.state.set_latest_block_hash(block_dict['hash'])

        if block_dict['blockNum'] > self.state.latest_block_num:
            self.state.latest_block_num = block_dict['blockNum']

    # Main Catchup function. Called at launch of node
    async def sync(self, sockets):
        self.in_catchup = True

        self.log.info('CATCHUP TIME...')

        current_height = await self.get_latest_block_height(random.choice(sockets))
        latest_block_stored = self.state.get_latest_block_num()

        latest_block_stored = max(latest_block_stored, 1)

        self.log.info(f'{current_height} / {latest_block_stored}')

        while current_height > latest_block_stored:

            await self.fetch_blocks(sockets, current_height)
            current_height = await self.get_latest_block_height(random.choice(sockets))
            latest_block_stored = self.state.get_latest_block_num()

            latest_block_stored = max(latest_block_stored, 1)

            self.log.info(f'{current_height} / {latest_block_stored}')

        self.in_catchup = False

        # Finds all of the blocks that were processed while syncing
        while len(self.blocks_to_process) > 0:
            b = self.blocks_to_process.pop(0)
            await self.find_and_store_block(b.blockNum, b.hash)

    # Secondary Catchup function. Called if a new block is created.
    async def intermediate_sync(self, block):
        if self.in_catchup:
            self.blocks_to_process.append(block)
        else:
            # store block directly
            await self.find_and_store_block(block.blockNum, block.hash)

    # Catchup for masternodes who already have storage and state is corrupted for some reason
    async def sync_blocks_with_state(self):
        if self.blocks is None:
            return

        last_block = self.blocks.get_last_n(1, CilantroStorageDriver.INDEX)[0]
        last_stored_block_num = last_block.get('blockNum')
        last_state_block_num = self.state.get_latest_block_num()

        while last_state_block_num < last_stored_block_num:
            last_state_block_num += 1
            block_dict = self.blocks.get_block(last_state_block_num)

            self.state.update_with_block(block_dict)
