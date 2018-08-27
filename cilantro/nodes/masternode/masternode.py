"""
    Masternode
    These are the entry points to the blockchain and pass messages on throughout the system. They are also the cold
    storage points for the blockchain once consumption is done by the network.

    They have no say as to what is 'right,' as governance is ultimately up to the network. However, they can monitor
    the behavior of nodes and tell the network who is misbehaving.
"""
from cilantro.constants.zmq_filters import WITNESS_MASTERNODE_FILTER, MASTERNODE_DELEGATE_FILTER
from cilantro.constants.masternode import STAGING_TIMEOUT
from cilantro.constants.ports import MN_NEW_BLOCK_PUB_PORT, MN_TX_PUB_PORT
from cilantro.constants.nodes import BLOCK_SIZE
from cilantro.constants.testnet import MAJORITY


from cilantro.protocol.states.decorators import *
from cilantro.protocol.states.state import State, StateInput

from cilantro.messages.consensus.block_contender import BlockContender
from cilantro.messages.block_data.transaction_data import TransactionReply, TransactionRequest
from cilantro.messages.block_data.block_metadata import BlockMetaDataRequest, BlockMetaDataReply
from cilantro.messages.envelope.envelope import Envelope
from cilantro.storage.blocks import BlockStorageDriver, BlockMetaData
from cilantro.messages.transaction.container import TransactionContainer
from cilantro.messages.transaction.ordering import OrderingContainer
from cilantro.messages.transaction.base import TransactionBase
from cilantro.messages.signals.kill_signal import KillSignal

from cilantro.storage.db import VKBook

import time
from cilantro.utils import LProcess
from multiprocessing import Queue

from cilantro.nodes import NodeBase
from cilantro.nodes.masternode.webserver import start_webserver
from cilantro.nodes.masternode.transaction_batcher import TransactionBatcher

MNNewBlockState = 'MNNewBlockState'
MNStagingState = 'MNStagingState'
MNBootState = 'MNBootState'


class Masternode(NodeBase):
    pass


class MNBaseState(State):

    @input(KillSignal)
    def handle_kill_sig(self, msg: KillSignal):
        # TODO check signature on kill sig make sure its trusted and such

        # TODO this is broken rn b/c only the TransactionBatcher process has a PUB port open
        raise NotImplementedError("This is broken right now. See comments.")

        self.log.important3("Masternode got kill signal! Relaying signal to all subscribed witnesses and delegates.")
        kill_sig = KillSignal.create()

        self.parent.composer.send_pub_msg(filter=WITNESS_MASTERNODE_FILTER, message=kill_sig, port=MN_TX_PUB_PORT)
        self.parent.composer.send_pub_msg(filter=MASTERNODE_DELEGATE_FILTER, port=MN_NEW_BLOCK_PUB_PORT, message=kill_sig)

        time.sleep(2)  # Allow time for messages to be composed before we teardown

        self.parent.teardown()

    @input_connection_dropped
    def conn_dropped(self, vk, ip):
        self.log.warning('({}:{}) has dropped'.format(vk, ip))

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

    def validate_block_contender(self, block: BlockContender) -> bool:
        """
        Helper method to validate a block contender. For a block contender to be valid it must:
        1) Have a provable merkle tree, ie. all nodes must be hash of (left child + right child)
        2) Be signed by at least 2/3 of the top 32 delegates
        3) Have the correct number of transactions
        4) Be a proposed child of the latest block in the database
        :param block_contender: The BlockContender to validate
        :return: True if the BlockContender is valid, false otherwise
        """
        # Development sanity checks
        # TODO -- in production these assertions should return False instead of raising an Exception
        assert len(block.merkle_leaves) >= 1, "Masternode got block contender with no nodes! {}".format(block)
        assert len(block.signatures) >= MAJORITY, \
            "Received a block contender with only {} signatures (which is less than a MAJORITY of {}"\
            .format(len(block.signatures), MAJORITY)

        assert len(block.merkle_leaves) == BLOCK_SIZE, \
            "Block contender has {} merkle leaves, but block size is {}!!!\nmerkle_leaves={}"\
            .format(len(block.merkle_leaves), BLOCK_SIZE, block.merkle_leaves)

        # TODO validate the sigs are actually from the top N delegates

        if not block.prev_block_hash == BlockStorageDriver.get_latest_block_hash():
            self.log.warning("BlockContender validation failed. Block contender's previous block hash {} does not "
                             "match DB's latest block hash {}"
                             .format(block.prev_block_hash, BlockStorageDriver.get_latest_block_hash()))
            return False

        return block.validate_signatures()


@Masternode.register_init_state
class MNBootState(MNBaseState):

    def reset_attrs(self):
        pass

    @enter_from_any
    def enter_any(self, prev_state):
        # Add publisher socket for sending NewBlockNotifications to delegates
        self.parent.composer.add_pub(ip=self.parent.ip, port=MN_NEW_BLOCK_PUB_PORT)

        # Add router socket
        self.parent.composer.add_router(ip=self.parent.ip)

        # Add dealer sockets to TESTNET_DELEGATES, for purposes of requesting block data
        for vk in VKBook.get_delegates():
            self.parent.composer.add_dealer(vk=vk)

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
        # Create and start web server
        self.log.notice("Masternode creating REST server on port 8080")
        self.parent.tx_queue = q = Queue()
        self.parent.server = LProcess(target=start_webserver, args=(q,))
        self.parent.server.start()

        # Create a worker to do transaction batching
        self.log.debug("Masternode creating transaction batcher process")
        self.parent.batcher = LProcess(target=TransactionBatcher,
                                       kwargs={'queue': q, 'signing_key': self.parent.signing_key,
                                               'ip': self.parent.ip})
        self.parent.batcher.start()

    @enter_from(MNNewBlockState)
    def enter_from_newblock(self, success=False):
        if not success:
            self.log.warning("NewBlockState transitioned back with failure!!!")

    @input_request(BlockContender)
    def handle_block_contender(self, block: BlockContender):
        # TODO this logic is not very clean. we are doing validation on blocks twice if a BlockContender is
        # received in RunState.
        if not self.validate_block_contender(block):
            return

        self.log.info("Masternode received block contender. Transitioning to NewBlockState".format(block))
        self.parent.transition(MNNewBlockState, block=block)
