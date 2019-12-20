from cilantro_ee.core.sockets.services import SubscriptionService, SocketStruct, Protocols
from cilantro_ee.services.block_fetch import BlockFetcher
from cilantro_ee.nodes.masternode.block_contender import BlockContender
from cilantro_ee.core.messages.message import Message
from cilantro_ee.core.messages.message_type import MessageType
from cilantro_ee.core.utils.block_sub_block_mapper import BlockSubBlockMapper
from cilantro_ee.services.storage.state import MetaDataStorage
from cilantro_ee.services.storage.master import CilantroStorageDriver
from cilantro_ee.contracts.sync import sync_genesis_contracts
from cilantro_ee.core.sockets.socket_book import SocketBook
from cilantro_ee.services.overlay.network import NetworkParameters, ServiceType
from cilantro_ee.services.storage.vkbook import VKBook
from cilantro_ee.constants.ports import MN_PUB_PORT
from cilantro_ee.core.crypto.wallet import Wallet

import time
import asyncio
import zmq
import zmq.asyncio


# Sends this to Transaction Batcher
class TransactionBatcherInformer:
    def __init__(self, ctx: zmq.asyncio.Context, wallet, ipc='ipc:///tmp/tx_batch_informer', linger=2000):
        self.wallet = wallet
        self.ctx = ctx

        self.socket = self.ctx.socket(zmq.PAIR)
        self.socket.setsockopt(zmq.LINGER, linger)
        self.socket.bind(ipc)

    async def send_ready(self):
        msg = Message.get_message_packed_2(msg_type=MessageType.READY)
        await self.socket.send(msg)

    async def send_burn_input_hashes(self, hashes):
        if len(hashes) > 0:
            msg = Message.get_message_packed_2(msg_type=MessageType.BURN_INPUT_HASHES, inputHashes=hashes)
            await self.socket.send(msg)


class BlockNotificationForwarder:
    pass


class BNKind:
    NEW = 0
    SKIP = 1
    FAIL = 2


class Block:
    def __init__(self, min_quorum, max_quorum, current_quorum,
                 subblocks_per_block, builders_per_block, contacts):

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
                 contacts=None,
                 gather_block_ejection_timeout=6*60*1000):

        self.subblock_subscription_service = subscription

        self.block_timeout = block_timeout
        self.contacts = contacts

        self.current_quorum = current_quorum
        self.min_quorum = min_quorum
        self.max_quorum = max_quorum

        self.gather_block_ejection_timeout = gather_block_ejection_timeout

        self.block_sb_mapper = BlockSubBlockMapper(self.contacts.masternodes)

        self.pending_block = Block(min_quorum=self.min_quorum,
                                   max_quorum=self.max_quorum,
                                   current_quorum=self.current_quorum,
                                   subblocks_per_block=self.block_sb_mapper.num_sb_per_block,
                                   builders_per_block=self.block_sb_mapper.num_sb_builders,
                                   contacts=self.contacts)

    async def gather_block(self):
        while not self.pending_block.started and len(self.subblock_subscription_service.received) == 0:
            await asyncio.sleep(0)

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
                        self.setup_new_block_contender()
                        return block, BNKind.SKIP
                    else:
                        # REGULAR
                        self.setup_new_block_contender()
                        return block, BNKind.NEW

                elif not self.pending_block.contender.is_consensus_possible():
                    # FAIL?
                    block = self.pending_block.contender.get_sb_data()
                    self.setup_new_block_contender()
                    return block, BNKind.FAIL

        # This will be hit if timeout is reached
        block = self.pending_block.contender.get_sb_data()
        # Check if we can adjust the quorum and return
        if self.pending_block.can_adjust_quorum():
            self.pending_block.current_quorum = self.pending_block.contender.get_current_quorum_reached()
            # REGULAR!
            self.setup_new_block_contender()
            return block, BNKind.NEW
        # Otherwise, fail the block
        else:
            # FAIL!
            self.setup_new_block_contender()
            return block, BNKind.FAIL

    def setup_new_block_contender(self):
        self.pending_block.started = False
        self.pending_block = Block(min_quorum=self.min_quorum,
                                   max_quorum=self.max_quorum,
                                   current_quorum=self.current_quorum,
                                   subblocks_per_block=self.block_sb_mapper.num_sb_per_block,
                                   builders_per_block=self.block_sb_mapper.num_sb_builders,
                                   contacts=self.contacts)


# Create socket base
class BlockAggregatorController:
    def __init__(self,
                 wallet,
                 socket_base,
                 vkbook,
                 ctx: zmq.asyncio.Context,
                 network_parameters=NetworkParameters(),
                 state: MetaDataStorage=MetaDataStorage(),
                 block_timeout=60*1000,
                 gather_block_ejection_timeout=5*60*1000):

        self.wallet = wallet
        self.vkbook = vkbook
        self.ctx = ctx
        self.network_parameters = network_parameters

        self.masternode_sockets = SocketBook(socket_base=socket_base,
                                             service_type=ServiceType.BLOCK_AGGREGATOR,
                                             ctx=self.ctx,
                                             network_parameters=self.network_parameters,
                                             phonebook_function=self.vkbook.contract.get_masternodes)

        self.delegate_sockets = SocketBook(socket_base=socket_base,
                                           service_type=ServiceType.SUBBLOCK_BUILDER_PUBLISHER,
                                           ctx=self.ctx,
                                           network_parameters=self.network_parameters,
                                           phonebook_function=self.vkbook.contract.get_delegates)

        self.driver = CilantroStorageDriver(key=self.wallet.signing_key(), vkbook=self.vkbook)

        self.state = state

        self.min_quorum = self.vkbook.delegate_quorum_min
        self.max_quorum = self.vkbook.delegate_quorum_max

        print(f'min q: {self.min_quorum} / max q: {self.max_quorum}')

        block_sb_mapper = BlockSubBlockMapper(self.vkbook.masternodes)
        my_vk = self.wallet.verifying_key()

        sb_nums = block_sb_mapper.get_list_of_sb_numbers(my_vk)

        self.sb_numbers = sb_nums
        self.sb_indices = block_sb_mapper.get_set_of_sb_indices(sb_nums)

        self.fetcher = BlockFetcher(wallet=self.wallet,
                                    ctx=self.ctx,
                                    blocks=self.driver,
                                    state=self.state)

        self.aggregator = BlockAggregator(subscription=None,
                                          block_timeout=block_timeout,
                                          min_quorum=self.min_quorum,
                                          max_quorum=self.max_quorum,
                                          current_quorum=self.max_quorum,
                                          contacts=self.vkbook,
                                          gather_block_ejection_timeout=gather_block_ejection_timeout)

        # Setup publisher socket for other masternodes to subscribe to
        self.pub_socket_address = self.network_parameters.resolve(socket_base=socket_base,
                                                                  service_type=ServiceType.BLOCK_AGGREGATOR, bind=True)
        self.pub_socket = self.ctx.socket(zmq.PUB)
        self.pub_socket.bind(str(self.pub_socket_address))

        self.informer = TransactionBatcherInformer(ctx=self.ctx, wallet=self.wallet)

        self.running = False

    async def start(self):
        await self.start_aggregator()

        await self.informer.send_ready()
        await self.send_ready()

    async def start_aggregator(self):
        subscription = SubscriptionService(ctx=self.ctx)
        current_quorum = 0

        # From SubBlockBuilderManager?
        for delegate in self.delegate_sockets.sockets.values():
            subscription.add_subscription(delegate)
            current_quorum += 1

        self.aggregator.subblock_subscription_service = subscription
        self.aggregator.current_quorum = current_quorum

        asyncio.ensure_future(self.aggregator.subblock_subscription_service.serve())

    async def process_blocks(self):
        while self.running:
            block, kind = await self.aggregator.gather_block()

            # if block type new block, store
            if kind == BNKind.NEW:
                self.driver.store_block(sub_blocks=block)

            # # Burn input hashes if needed
            # await self.informer.send_burn_input_hashes(
            #     hashes=self.get_input_hashes_to_burn(block)
            # )
            #
            # # Reset Block Contender on Aggregator
            # self.aggregator.setup_new_block_contender()
            #
            # # Send block notification to where it has to go
            # block_notification = self.serialize_block(block, kind)
            # self.pub_socket.send(block_notification)

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

    # raghu - ? is it sub_blocks
    def get_input_hashes_to_burn(self, sub_blocks):
        sbs = []
        for i in self.sb_indices:
            sb = sub_blocks[i]
            if type(sb) != dict:
                sb = sb.to_dict()

            if sb['subBlockNum'] in self.sb_numbers:
                sbs.append(sb)

        return sbs

        # return [sb_dicts[i]['inputHash'] for i in self.sb_indices if sb_dicts[i]['subBlockNum'] in self.sb_numbers]

    async def send_ready(self):
        ready = Message.get_signed_message_packed_2(
            wallet=self.wallet,
            msg_type=MessageType.READY)

        await self.pub_socket.send(ready)

    def stop(self):
        self.aggregator.subblock_subscription_service.stop()
