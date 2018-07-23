"""
    Masternode
    These are the entry points to the blockchain and pass messages on throughout the system. They are also the cold
    storage points for the blockchain once consumption is done by the network.

    They have no say as to what is 'right,' as governance is ultimately up to the network. However, they can monitor
    the behavior of nodes and tell the network who is misbehaving.
"""
from cilantro import Constants
from cilantro.nodes import NodeBase
from cilantro.protocol.statemachine import *
from cilantro.messages import *
from aiohttp import web
from cilantro.db import *


MNNewBlockState = 'MNNewBlockState'


class Masternode(NodeBase):

    async def route_http(self, request):
        # self.log.debug("Got request {}".format(request))
        raw_data = await request.content.read()

        # self.log.debug("Got raw_data: {}".format(raw_data))
        container = TransactionContainer.from_bytes(raw_data)

        # self.log.debug("Got container: {}".format(container))
        tx = container.open()
        self.log.debug("Masternode got tx: {}".format(tx))

        import traceback
        try:
            self.state.call_input_handler(message=tx, input_type=StateInput.INPUT)
            return web.Response(text="Successfully published transaction: {}".format(tx))
        except Exception as e:
            self.log.error("\n Error publishing HTTP request...err = {}".format(traceback.format_exc()))
            return web.Response(text="fukt up processing request with err: {}".format(e))


class MNBaseState(State):
    @input(TransactionBase)
    def handle_tx(self, tx: TransactionBase):
        self.log.debug("mn about to pub for tx {}".format(tx))  # debug line
        self.parent.composer.send_pub_msg(filter=Constants.ZmqFilters.WitnessMasternode, message=tx)

    @input_request(BlockContender)
    def handle_block_contender(self, block: BlockContender):
        self.log.warning("Current state not configured to handle block contender")
        self.log.debug('Block: {}'.format(block))

    @input(TransactionReply)
    def handle_tx_reply(self, reply: TransactionReply):
        self.log.warning("Current state not configured to handle transaction reply")
        self.log.debug('Reply: {}'.format(reply))

    @input(TransactionRequest)
    def handle_tx_request(self, request: TransactionRequest):
        self.log.debug("Masternode received TransactionRequest request: {}".format(request))
        tx_blobs = BlockStorageDriver.get_raw_transactions(request.tx_hashes)
        reply = TransactionReply.create(raw_transactions=tx_blobs)
        return reply

    @input(BlockMetaDataRequest)
    def handle_blockmeta_request(self, request: BlockMetaDataRequest):
        self.log.debug("Masternode received BlockMetaDataRequest: {}".format(request))

        # Get a list of block hashes up until this most recent block
        # TODO get_child_block_hashes return an error/assertion/something if block cannot be found
        child_hashes = BlockStorageDriver.get_child_block_hashes(request.current_block_hash)
        self.log.debug("Got descended block hashes {} for block hash {}".format(child_hashes, request.current_block_hash))

        # If this hash could not be found or if it was the latest hash, no need to lookup any blocks
        if not child_hashes:
            self.log.debug("Requested block hash {} is already up to date".format(request.current_block_hash))
            reply = BlockMetaDataReply.create(block_metas=None)
            return reply

        # Build a BlockMetaData object for each descendant block
        block_metas = []
        for block_hash in child_hashes:
            block_data = BlockStorageDriver.get_block(hash=block_hash)
            meta = BlockMetaData.create(**block_data)  # TODO make sure all the kwargs match up with the create API
            block_metas.append(meta)

        reply = BlockMetaDataReply.create(block_metas=block_metas)
        return reply


@Masternode.register_init_state
class MNBootState(MNBaseState):
    def reset_attrs(self):
        pass

    @enter_from_any
    def enter_any(self, prev_state):
        self.log.debug("MN IP: {}".format(self.parent.ip))

        # Add publisher socket
        self.parent.composer.add_pub(ip=self.parent.ip)

        # Add router socket
        self.parent.composer.add_router(ip=self.parent.ip)

        # Add dealer sockets to delegates, for purposes of requesting block data
        for vk in VKBook.get_delegates():
            self.parent.composer.add_dealer(vk=vk)

        # Once done booting, transition to run
        self.parent.transition(MNRunState)

    @exit_to_any
    def exit_any(self, next_state):
        self.log.debug("Bootstate exiting for next state {}".format(next_state))

    @input(TransactionBase)
    def handle_tx(self, tx: TransactionBase):
        self.log.warning("MN BootState not configured to handle transactions")

    @input(TransactionRequest)
    def handle_tx_request(self, request: TransactionRequest):
        self.log.warning("MN BootState not ready to handle TransactionRequests")

    @input(BlockMetaDataRequest)
    def handle_blockmeta_request(self, request: BlockMetaDataRequest):
        self.log.warning("MN BootState not ready to handle BlockMetaDataRequest")


@Masternode.register_state
class MNRunState(MNBaseState):
    def reset_attrs(self):
        pass

    @enter_from(MNBootState)
    def enter_from_boot(self, prev_state):
        # Create web server
        self.log.debug("Creating web server")
        server = web.Server(self.parent.route_http)
        server_future = self.parent.loop.create_server(server, "0.0.0.0", 8080)
        self.parent.tasks.append(server_future)

    @enter_from(MNNewBlockState)
    def enter_from_newblock(self, success=False):
        if not success:
            # this should really just be a warning, but for dev we log it as an error
            self.log.error("\n\nNewBlockState transitioned back with failure!!!\n\n")

    @input_request(BlockContender)
    def handle_block_contender(self, block: BlockContender):
        self.log.info("Masternode received block contender. Transitioning to NewBlockState".format(block))
        self.parent.transition(MNNewBlockState, block=block)
