"""
    Masternode
    These are the entry points to the blockchain and pass messages on throughout the system. They are also the cold
    storage points for the blockchain once consumption is done by the network.

    They have no say as to what is 'right,' as governance is ultimately up to the network. However, they can monitor
    the behavior of nodes and tell the network who is misbehaving.
"""
from cilantro.constants.zmq_filters import WITNESS_MASTERNODE_FILTER, MASTERNODE_DELEGATE_FILTER
from cilantro.constants.masternode import STAGING_TIMEOUT
from cilantro.nodes import NodeBase

from cilantro.protocol.states.decorators import *
from cilantro.protocol.states.state import State, StateInput

from cilantro.messages.transaction.container import TransactionContainer
from cilantro.messages.consensus.block_contender import BlockContender
from cilantro.messages.block_data.transaction_data import TransactionReply, TransactionRequest
from cilantro.messages.block_data.block_metadata import BlockMetaDataRequest, BlockMetaDataReply
from cilantro.messages.envelope.envelope import Envelope
from cilantro.storage.blocks import BlockStorageDriver, BlockMetaData
from cilantro.messages.transaction.ordering import OrderingContainer
from cilantro.messages.transaction.base import TransactionBase
from cilantro.messages.signals.kill_signal import KillSignal

from aiohttp import web
import time
import asyncio
import traceback
from cilantro.storage.db import VKBook
from collections import deque

from cilantro.utils import LProcess
from multiprocessing import Queue
from cilantro.nodes.masternode.webserver import start_webserver
from cilantro.nodes.masternode.transaction_batcher import TransactionBatcher

MNNewBlockState = 'MNNewBlockState'
MNStagingState = 'MNStagingState'
MNBootState = 'MNBootState'


class Masternode(NodeBase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Define 'global' properties, shared among all states
        self.tx_queue = deque()  # A queue of transactions sent by users to the Masternode via a REST endpoint

    async def route_http(self, request):
        raw_data = await request.content.read()

        if request.path == '/teardown-network':
            self.log.important("Masternode got kill message from rest endpoint!")
            tx = KillSignal.create()
        else:
            container = TransactionContainer.from_bytes(raw_data)
            tx = container.open()
        try:
            self.state.call_input_handler(message=tx, input_type=StateInput.INPUT)
            return web.Response(text="Successfully published transaction: {}".format(tx))
        except Exception as e:
            self.log.error("\n Error publishing HTTP request...err = {}".format(traceback.format_exc()))
            return web.Response(text="problem processing request with err: {}".format(e))


class MNBaseState(State):

    @input(KillSignal)
    def handle_kill_sig(self, msg: KillSignal):
        # TODO check signature on kill sig make sure its trusted and such
        self.log.important3("Masternode got kill signal! Relaying signal to all subscribed witnesses and delegates.")
        kill_sig = KillSignal.create()

        self.parent.composer.send_pub_msg(filter=WITNESS_MASTERNODE_FILTER, message=kill_sig)
        self.parent.composer.send_pub_msg(filter=MASTERNODE_DELEGATE_FILTER, message=kill_sig)

        time.sleep(2)  # Allow time for messages to be composed before we teardown

        self.parent.teardown()

    @input_connection_dropped
    def conn_dropped(self, vk, ip):
        self.log.warning('({}:{}) has dropped'.format(vk, ip))

    @input(TransactionBase)
    def handle_tx(self, tx: TransactionBase):
        oc = OrderingContainer.create(tx=tx, masternode_vk=self.parent.verifying_key)
        self.log.spam("mn about to pub for tx {}".format(tx))  # debug line
        self.parent.composer.send_pub_msg(filter=WITNESS_MASTERNODE_FILTER, message=oc)

    @input_request(BlockContender)
    def handle_block_contender(self, block: BlockContender):
        self.log.warning("Current state not configured to handle block contender")
        self.log.debug('Block: {}'.format(block))

    @input(TransactionReply)
    def handle_tx_reply(self, reply: TransactionReply):
        self.log.warning("Current state not configured to handle transaction reply")
        self.log.debug('Reply: {}'.format(reply))

    @input_request(TransactionRequest)
    def handle_tx_request(self, request: TransactionRequest):
        self.log.debug("Masternode received TransactionRequest request: {}".format(request))
        tx_blobs = BlockStorageDriver.get_raw_transactions(request.tx_hashes)
        reply = TransactionReply.create(raw_transactions=tx_blobs)
        return reply

    @input_timeout(TransactionRequest)
    def handle_tx_request_timeout(self, request: TransactionRequest, envelope: Envelope):
        self.log.warning("Current state {} not configured to handle tx request timeout".format(self))

    @input_request(BlockMetaDataRequest)
    def handle_blockmeta_request(self, request: BlockMetaDataRequest, envelope: Envelope):
        vk = envelope.seal.verifying_key
        assert vk in VKBook.get_delegates(), "Got BlockMetaDataRequest from VK {} not in delegate VKBook!".format(vk)
        self.log.notice("Masternode received BlockMetaDataRequest from delegate {}\n...request={}".format(vk, request))

        # Get a list of block hashes up until this most recent block
        # TODO get_child_block_hashes return an error/assertion/something if block cannot be found
        child_hashes = BlockStorageDriver.get_child_block_hashes(request.current_block_hash)
        self.log.debugv("Got descendant block hashes {} for block hash {}".format(child_hashes, request.current_block_hash))

        # If this hash could not be found or if it was the latest hash, no need to lookup any blocks
        if not child_hashes:
            self.log.debug("Requested block hash {} is already up to date".format(request.current_block_hash))
            reply = BlockMetaDataReply.create(block_metas=None)
            return reply

        # Build a BlockMetaData object for each descendant block
        block_metas = []
        for block_hash in child_hashes:
            block_data = BlockStorageDriver.get_block(hash=block_hash, include_number=False)
            meta = BlockMetaData.create(**block_data)
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

        # Add dealer sockets to TESTNET_DELEGATES, for purposes of requesting block data
        for vk in VKBook.get_delegates():
            self.parent.composer.add_dealer(vk=vk)

        # Create and start web server
        # TODO put this in run state, or somewhere after we exit staging
        self.log.info("Creating REST server on port 8080")
        self.parent.tx_queue = q = Queue()   # perhaps there is a better name than 'rest_q'
        self.parent.server = LProcess(target=start_webserver, args=(q,))
        self.parent.server.start()

        # Create a worker to do turnt raghu transaction batching stuff
        # TODO put this in run state, or somewhere after we exit staging
        # TODO perhaps there is a better name that "batcher"
        self.parent.batcher = LProcess(target=TransactionBatcher, kwargs={'queue': q, 'signing_key': self.parent.signing_key})
        self.parent.batcher.start()

        # self.log.info("Creating REST server on port 8080")
        # server = web.Server(self.parent.route_http)
        # server_future = self.parent.loop.create_server(server, "0.0.0.0", 8080)
        # self.parent.tasks.append(server_future)

        # Once done booting, transition to staging
        self.parent.transition(MNStagingState)

    @exit_to_any
    def exit_any(self, next_state):
        self.log.debug("Bootstate exiting for next state {}".format(next_state))

    @input(TransactionBase)
    def handle_tx(self, tx: TransactionBase):
        self.log.warning("MN BootState not configured to handle transactions")

    @input(TransactionRequest)
    def handle_tx_request(self, request: TransactionRequest):
        self.log.warning("MN BootState not ready to handle TransactionRequests")

    @input_request(BlockMetaDataRequest)
    def handle_blockmeta_request(self, request: BlockMetaDataRequest, envelope: Envelope):
        self.log.warning("MN BootState not ready to handle BlockMetaDataRequest")


@Masternode.register_state
class MNStagingState(MNBaseState):
    """
    Staging State allows the Masternode to defer publishing transactions to the network until is ready.
    The network is considered 'ready' when 2/3 of the TESTNET_DELEGATES have the latest blockchain state.
    """

    def reset_attrs(self):
        self.ready_delegates = set()

    @timeout_after(STAGING_TIMEOUT)
    def timeout(self):
        self.log.fatal("Masternode failed to exit StagingState before timeout of {}! Exiting system.".format(STAGING_TIMEOUT))
        self.log.fatal("Ready delegates: {}".format(self.ready_delegates))
        exit()

    @enter_from_any
    def enter_any(self):
        self.reset_attrs()

    # TODO remove this. keeping it for dev purposes for a bit
    @input(TransactionBase)
    def handle_tx(self, tx: TransactionBase):
        raise Exception("OH NO! This should not get called anymore. TransactionBase processing should be done by ")

    @input_request(BlockMetaDataRequest)
    def handle_blockmeta_request(self, request: BlockMetaDataRequest, envelope: Envelope):
        reply = super().handle_blockmeta_request(request, envelope)
        self.parent.composer.send_reply(message=reply, request_envelope=envelope)

        if not reply.block_metas:
            vk = envelope.seal.verifying_key
            self.log.notice("Delegate with vk {} has the latest blockchain state!".format(vk))
            self.ready_delegates.add(vk)
            self._check_ready()

    def _check_ready(self):
        """
        Checks if the system is 'ready' (as described in the MNStagingState docstring). If all conditions are met,
        this function will transition to MNRunState.
        """
        # TODO for dev we require all delegates online. IRL a 2/3 majority should suffice
        # majority = VKBook.get_delegate_majority()
        majority = len(VKBook.get_delegates())

        num_ready = len(self.ready_delegates)

        if num_ready >= majority:
            self.log.important("{}/{} Delegates are at the latest blockchain state! MN exiting StagingState."
                               "\n(Ready Delegates = {})".format(num_ready, len(VKBook.get_delegates()), self.ready_delegates))
            self.parent.transition(MNRunState)
            return
        else:
            self.log.notice("Only {} of {} required delegate majority ready. MN remaining in StagingState".format(num_ready, majority))


@Masternode.register_state
class MNRunState(MNBaseState):
    def reset_attrs(self):
        pass

    @enter_from_any
    def enter_any(self):
        # TODO start web server and consumer proc here
        pass
        # TODO remove this
        # if not self.parent.tx_queue:
        #     return

        # self.log.notice("Flushing queue of {} transactions".format(len(self.parent.tx_queue)))
        # for tx in self.parent.tx_queue:
        #     self.handle_tx(tx)
        # self.parent.tx_queue.clear()

    @enter_from(MNNewBlockState)
    def enter_from_newblock(self, success=False):
        if not success:
            # this should really just be a warning, but for dev we log it as an error
            self.log.fatal("\n\nNewBlockState transitioned back with failure!!!\n\n")

    @input_request(BlockContender)
    def handle_block_contender(self, block: BlockContender):
        self.log.info("Masternode received block contender. Transitioning to NewBlockState".format(block))
        self.parent.transition(MNNewBlockState, block=block)
