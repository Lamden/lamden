from cilantro_ee.core.sockets import SocketBook
from cilantro_ee.storage.vkbook import PhoneBook
from cilantro_ee.core.top import TopBlockManager
from cilantro_ee.protocol.wallet import Wallet
from cilantro_ee.core.messages.message import Message, MessageType
from cilantro_ee.protocol.comm.services import get, defer
import zmq.asyncio
import asyncio
from collections import Counter
import time


class ConfirmationCounter(Counter):
    def top_item(self):
        return self.most_common()[0][0]

    def top_count(self):
        return self.most_common()[0][1]


class BlockFetcher:
    def __init__(self, wallet: Wallet, ctx: zmq.Context, top=TopBlockManager()):
        self.masternodes = SocketBook(None, PhoneBook.contract.get_masternodes)
        self.delegates = SocketBook(None, PhoneBook.contract.get_delegates)
        self.top = top
        self.wallet = wallet
        self.ctx = ctx

    async def find_missing_block_indexes(self, confirmations=3, timeout=3000):
        await self.masternodes.refresh()

        responses = ConfirmationCounter()

        futures = []
        # Fire off requests to all nodes on the network
        for master in self.masternodes.sockets.values():
            f = asyncio.ensure_future(self.get_latest_block_height(master))
            futures.append(f)

        # Iterate through the status of the
        now = time.time()
        while responses.top_count() < confirmations or time.time() - now > timeout:
            await defer()
            for f in futures:
                if f.done():
                    responses.update([f.result()])

        return responses.top_item()

    async def get_latest_block_height(self, socket):
        request = Message.get_signed_message_packed_2(wallet=self.wallet,
                                                      msg_type=MessageType.LATEST_BLOCK_HEIGHT_REQUEST,
                                                      timestamp=int(time.time()))

        response = await get(socket_id=socket, msg=request, ctx=self.ctx, timeout=3000, retries=0, dealer=True)

        _, unpacked, _, _, _ = Message.unpack_message_2(response)

        return unpacked.blockHeight

    def fetch_blocks(self, starting_block_number=0):
        pass
