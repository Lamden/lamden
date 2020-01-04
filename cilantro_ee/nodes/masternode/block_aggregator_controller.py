import zmq.asyncio

from cilantro_ee.storage.state import MetaDataStorage
from cilantro_ee.storage.master import CilantroStorageDriver

from cilantro_ee.messages.message_type import MessageType
from cilantro_ee.messages.message import Message

from cilantro_ee.networking.parameters import ServiceType, NetworkParameters
from cilantro_ee.crypto.block_sub_block_mapper import BlockSubBlockMapper

from cilantro_ee.nodes.masternode.block_aggregator import BlockAggregator, BNKind


# Create socket base
class BlockAggregatorController:
    def __init__(self,
                 wallet,
                 socket_base,
                 vkbook,
                 ctx: zmq.asyncio.Context,
                 network_parameters=NetworkParameters(),
                 state: MetaDataStorage=MetaDataStorage(),
                 block_timeout=60*1000):

        self.wallet = wallet
        self.vkbook = vkbook
        self.ctx = ctx
        self.network_parameters = network_parameters

        self.driver = CilantroStorageDriver(key=self.wallet.signing_key(), vkbook=self.vkbook)

        self.state = state

        self.min_quorum = self.vkbook.delegate_quorum_min
        self.max_quorum = self.vkbook.delegate_quorum_max

        block_sb_mapper = BlockSubBlockMapper(self.vkbook.masternodes)

        sb_nums = block_sb_mapper.get_list_of_sb_numbers(self.wallet.verifying_key())

        self.sb_numbers = sb_nums
        self.sb_indices = block_sb_mapper.get_set_of_sb_indices(sb_nums)

        # Modify block agg to take an async inbox instead
        self.aggregator = BlockAggregator(
            socket_id=self.network_parameters.resolve(socket_base, ServiceType.BLOCK_AGGREGATOR_CONTROLLER, bind=True),
            ctx=self.ctx,
            block_timeout=block_timeout,
            min_quorum=self.min_quorum,
            max_quorum=self.max_quorum,
            current_quorum=self.max_quorum,
            contacts=self.vkbook
        )

        self.running = False

    async def start(self):
        await self.aggregator.start()
        self.running = True

    async def process_sbcs_from_delegates(self):
        block, kind = await self.aggregator.gather_block()

        # Burn input hashes if needed
        if len(block) > 0:
            notification = self.driver.get_block_dict(block, kind)

            print(notification)

            owners = []
            if kind == BNKind.NEW:
                self.driver.store_block(sub_blocks=block)
                owners = [m for m in self.vkbook.masternodes]
                notification['newBlock'] = None

            notification['blockOwners'] = owners

            if kind == BNKind.SKIP:
                notification['emptyBlock'] = None

            if kind == BNKind.FAIL:
                notification['failedBlock'] = None

            block_notification = Message.get_message_packed_2(
                msg_type=MessageType.BLOCK_NOTIFICATION,
                **notification
            )

            return block_notification, kind

    def stop(self):
        # Order matters here
        self.running = False
        self.aggregator.running = False
        self.aggregator.pending_block.started = True
        self.aggregator.async_queue.stop()
