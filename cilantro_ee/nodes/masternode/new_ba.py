from cilantro_ee.core.sockets.services import SubscriptionService, SocketStruct, Protocols
from cilantro_ee.services.block_fetch import BlockFetcher
from cilantro_ee.nodes.masternode.block_contender import BlockContender
from cilantro_ee.core.messages.message import Message
from cilantro_ee.core.messages.message_type import MessageType
from cilantro_ee.services.storage.state import MetaDataStorage
from cilantro_ee.services.storage.master import CilantroStorageDriver
from cilantro_ee.contracts.sync import sync_genesis_contracts
from cilantro_ee.core.sockets.socket_book import SocketBook
from cilantro_ee.services.storage.vkbook import PhoneBook
from cilantro_ee.constants.system_config import *

import time
import asyncio
import zmq
import zmq.asyncio


# Sends this to Transaction Batcher
class TransactionBatcherInformer:
    def __init__(self, socket_id, ctx: zmq.asyncio.Context, wallet, linger=2000):
        if socket_id.protocol == Protocols.TCP:
            socket_id.id = '*'

        self.wallet = wallet
        self.ctx = ctx
        self.socket = self.ctx.socket(zmq.PAIR)
        self.socket.setsockopt(zmq.LINGER, linger)
        self.socket.bind(str(socket_id))

    async def send_ready(self):
        ready = Message.get_message_packed_2(msg_type=MessageType.READY)
        await self.socket.send(ready)

    async def send_burn_input_hashes(self, hashes):
        if len(hashes) > 0:
            burn_input_hashes = Message.get_message_packed_2(msg_type=MessageType.BURN_INPUT_HASHES, inputHashes=hashes)
            self.socket.send(burn_input_hashes)


class BlockNotificationForwarder:
    pass


class BNKind:
    NEW = 0
    SKIP = 1
    FAIL = 2


class Block:
    def __init__(self, min_quorum, max_quorum, current_quorum, subblocks_per_block=NUM_SB_PER_BLOCK, builders_per_block=NUM_SB_BUILDERS, contacts=PhoneBook):
        self.contender = BlockContender(subblocks_per_block, builders_per_block, contacts=contacts)
        self.started = False
        self.current_quorum = current_quorum
        self.min_quorum = min_quorum
        self.max_quorum = max_quorum

    def consensus_is_reached(self):
        if self.contender.is_consensus_reached() or self.contender.get_current_quorum_reached() >= self.current_quorum:
            return True
        return False

    def can_adjust_quorum(self):
        current_block_quorum = self.contender.get_current_quorum_reached()
        return current_block_quorum >= self.min_quorum and current_block_quorum >= (9 * self.current_quorum // 10)


class BlockAggregator:
    def __init__(self, subscription: SubscriptionService,
                 block_timeout=60*1000,
                 current_quorum=0,
                 min_quorum=0,
                 max_quorum=1,
                 subblocks_per_block=NUM_SB_PER_BLOCK,
                 builders_per_block=NUM_SB_BUILDERS,
                 contacts=PhoneBook):

        self.subblock_subscription_service = subscription

        self.block_timeout = block_timeout
        self.contacts = contacts

        self.current_quorum = current_quorum
        self.min_quorum = min_quorum
        self.max_quorum = max_quorum

        self.pending_block = Block(min_quorum=self.min_quorum,
                                   max_quorum=self.max_quorum,
                                   current_quorum=self.current_quorum,
                                   subblocks_per_block=subblocks_per_block,
                                   builders_per_block=builders_per_block,
                                   contacts=contacts)

    async def gather_block(self):
        # Wait until queue has at least one then have some bool flag
        while not self.pending_block.started and len(self.subblock_subscription_service.received) == 0:
            asyncio.sleep(0)

        self.pending_block.started = True

        start_time = time.time()

        while time.time() - start_time < self.block_timeout:
            if len(self.subblock_subscription_service.received) > 0:
                # Pop the next SBC off of the subscription LIFO queue
                sbc, _ = self.subblock_subscription_service.received.pop(0)
                msg_type, msg, sender, timestamp, is_verified = Message.unpack_message_2(sbc)

                # Deserialize it and add it to the pending block
                self.pending_block.contender.add_sbc(sender, msg)

                if self.pending_block.consensus_is_reached():
                    block = self.pending_block.contender.get_sb_data()
                    if self.pending_block.contender.is_empty():
                        # SKIP!
                        return block, BNKind.SKIP
                    else:
                        # REGULAR
                        return block, BNKind.NEW

                elif not self.pending_block.contender.is_consensus_possible():
                    # FAIL?
                    block = self.pending_block.contender.get_sb_data()
                    return block, BNKind.FAIL

        # This will be hit if timeout is reached
        block = self.pending_block.contender.get_sb_data()
        # Check if we can adjust the quorum and return
        if self.pending_block.can_adjust_quorum():
            self.pending_block.current_quorum = self.pending_block.contender.get_current_quorum_reached()
            # REGULAR!
            return block, BNKind.NEW
        # Otherwise, fail the block
        else:
            # FAIL!
            return block, BNKind.FAIL

    def setup_new_block_contender(self):
        self.pending_block = Block(min_quorum=self.min_quorum,
                                   max_quorum=self.max_quorum,
                                   current_quorum=self.current_quorum)


class BlockAggregatorController:
    def __init__(self,
                 state: MetaDataStorage,
                 driver: CilantroStorageDriver,
                 ctx: zmq.asyncio.Context,
                 informer_socket: SocketStruct,
                 pub_port: int,
                 wallet, sb_idx, mn_idx, min_quorum, max_quorum,
                 masternode_sockets=SocketBook(None, PhoneBook.contract.get_masternodes),
                 delegate_sockets=SocketBook(None, PhoneBook.contract.get_delegates),
                 contacts=PhoneBook):

        self.state = state
        self.driver = driver
        self.wallet = wallet
        self.ctx = ctx

        self.sb_idx = sb_idx
        self.mn_idx = mn_idx

        self.contacts = contacts
        self.min_quorum = self.contacts.delegate_quorum_min
        self.max_quorum = self.contacts.delegate_quorum_max

        self.masternode_sockets = masternode_sockets
        self.delegate_sockets = delegate_sockets

        self.fetcher = BlockFetcher(wallet=self.wallet,
                                    ctx=self.ctx,
                                    blocks=self.driver,
                                    state=self.state)

        self.aggregator = None

        self.pub_socket = self.ctx.socket(zmq.PUB)
        self.pub_socket.bind('tcp://*:{}'.format(pub_port))

        self.informer = TransactionBatcherInformer(
            socket_id=informer_socket
        )

        self.running = False

    async def start(self):
        sync_genesis_contracts()
        await self.fetcher.sync()

        await self.start_aggregator()

        await self.informer.send_ready()
        await self.send_ready()

    async def start_aggregator(self):
        subscription = SubscriptionService(ctx=self.ctx)
        current_quorum = 0

        for delegate in self.delegate_sockets.sockets.values():
            subscription.add_subscription(delegate)
            current_quorum += 1

        self.aggregator = BlockAggregator(subscription=subscription,
                                          min_quorum=self.min_quorum,
                                          max_quorum=self.max_quorum,
                                          current_quorum=current_quorum)

    async def process_blocks(self):
        while self.running:
            block, kind = await self.aggregator.gather_block()

            # if block type new block, store
            if kind == BNKind.NEW:
                self.driver.store_block(sub_blocks=block)

            # Burn input hashes if needed
            await self.informer.send_burn_input_hashes(
                hashes=self.get_input_hashes_to_burn(block)
            )

            # Reset Block Contender on Aggregator
            self.aggregator.setup_new_block_contender()

            # Send block notification to where it has to go
            block_notification = self.serialize_block(block, kind)
            self.pub_socket.send(block_notification)

    def forward_new_block_notifications(self, sender, msg):
        blocknum = msg.blockNum

        if (blocknum > self.state.latest_block_num + 1) and \
                (msg.type.which() == "newBlock"):
            self.fetcher.intermediate_sync(msg)

    def serialize_block(self, block, kind):
        if kind == BNKind.NEW:
            block['newBlock'] = None
        elif kind == BNKind.SKIP:
            block['emptyBlock'] = None
        else:
            block['failedBlock'] = None

        block_notification = Message.get_signed_message_packed_2(
            wallet=self.wallet,
            msg_type=MessageType.BLOCK_NOTIFICATION,
            **block)

        return block_notification

    def get_input_hashes_to_burn(self, block):
        if block['firstSbIdx'] + self.sb_idx == self.mn_idx:
            return block['inputHashes'][self.sb_idx]
        return []

    async def send_ready(self):
        ready = Message.get_signed_message_packed_2(
            wallet=self.wallet,
            msg_type=MessageType.READY)

        await self.pub_socket.send(ready)
