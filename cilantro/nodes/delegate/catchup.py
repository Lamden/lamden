from cilantro.nodes.delegate.delegate import Delegate, DelegateBaseState
from cilantro.protocol.states.decorators import input, input_timeout, exit_to_any, enter_from_any, timeout_after
from cilantro.storage.blocks import BlockStorageDriver
from cilantro.messages.block_data.block_metadata import BlockMetaDataReply, BlockMetaDataRequest, NewBlockNotification
from cilantro.messages.block_data.transaction_data import TransactionReply, TransactionRequest
from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.transaction.contract import ContractTransaction
from cilantro.storage.db import VKBook
from cilantro.constants.delegate import CATCHUP_TIMEOUT, BLOCK_REQ_TIMEOUT, TX_REQ_TIMEOUT
from cilantro.utils.hasher import Hasher

DelegateBootState = "DelegateBootState"
DelegateInterpretState = "DelegateInterpretState"
DelegateConsensusState = "DelegateConsensusState"


"""
TODO optimize catchup procedure. Move away from this sluggish sequential block requesting. 

We are currently fetching transactions blobs block by block. We wait to interpret all of a block transactions before 
requesting the transactions for the next block.
(ie "give me all the TXs for block 1...ok now process those, ok next give me all TXs for block 2"...and so on)

This can be made more efficient to request up to N txs from up to B pending blocks async, and piecing together as we go.
This requires a more efficient data structure that can store all transactions across all blocks, access these by hash in
O(1), but also check if all transactions from a given block hash have been fetched in O(1).. Naively, using a hash table
of tx_hash-->tx_blob satisfies requirement 1, but takes O(n) to check if all transactions have been fetched for a given
block. 
"""


@Delegate.register_state
class DelegateCatchupState(DelegateBaseState):

    def reset_attrs(self):
        self.new_blocks = []  # A queue of blocks to fetch
        self.current_block = None  # The current block being fetched

        # TODO engineer executors to provide original request env along with reply so we don't have to do this
        self.current_request = None  # The current TransactionRequest which we want a TransactionReply for

    @timeout_after(CATCHUP_TIMEOUT)
    def timeout(self):
        self.log.fatal("CatchUp state exceeded timeout of {} seconds!".format(CATCHUP_TIMEOUT))
        self.log.fatal("current block hash: {}\ncurrent_block: {}\npending blocks: {}\n"
                       .format(self.parent.current_hash, self.current_block, self.new_blocks))
        self.log.fatal("System exiting.")
        exit()

    @enter_from_any
    def enter_any(self, prev_state):
        self.reset_attrs()
        self._request_update()

    @exit_to_any
    def exit_any(self, next_state):
        assert self.parent.interpreter.queue_size == 0, 'Delegate exiting catchup state with nonempty interpreter queue'

        self.parent.current_hash = BlockStorageDriver.get_latest_block_hash()
        self.log.info("CatchupState exiting. Current block hash set to {}".format(self.parent.current_hash))

    # TODO -- prune the transaction queue of transactions we get from requested blocks
    @input(BlockMetaDataReply)
    def handle_blockmeta_reply(self, reply: BlockMetaDataReply):
        self.log.debug("Delegate got BlockMetaDataReply: {}".format(reply))

        if not reply.block_metas:
            self.log.success("Delegate done updated state to latest block hash {}".format(self.parent.current_hash))
            self.parent.transition(DelegateInterpretState)
            return

        self.new_blocks += reply.block_metas
        self._update_next_block()

    @input(TransactionReply)
    def handle_tx_reply(self, reply: TransactionReply, envelope: Envelope):
        assert self.current_request, "Got TransactionReply, but self.current_request is not set!"
        request = self.current_request
        self.log.debugv("Delegate got tx reply {} with original request {}".format(reply, request))

        # Verify that the transactions blobs in the reply match the requested hashes in the request
        if not reply.validate_matches_request(request):
            self.log.error("Could not verify transactions with:\nrequest: {}\nreply: {}".format(request, reply))
            return

        # Verify that the transactions match the merkle leaves in the block meta
        if request.tx_hashes() != self.current_block.merkle_leaves:
            self.log.error("Requested TX hashes\n{}\ndoes not match current block's merkle leaves\n{}"
                           .format(request.tx_hashes, self.current_block))
            return

        # Interpret the transactions
        for contract_blob in reply.transactions:
            self.parent.interpreter.interpret(ContractTransaction.from_bytes(contract_blob), async=False)
            self.parent.pending_txs.remove(Hasher.hash(contract_blob))
        self.parent.interpret.flush(update_state=True)

        # Finally, store this new block and update our current block hash. Reset self.current_block, update next block
        BlockStorageDriver.store_block_from_meta(self.current_block)
        self.current_block, self.current_request = None, None
        self._update_next_block()

    @input(NewBlockNotification)
    def handle_new_block_notif(self, notif: NewBlockNotification):
        self.log.notice("Delegate got new block notification with hash {}\nprev_hash {}]\nand our current hash = {}"
                        .format(notif.block_hash, notif.prev_block_hash, self.parent.current_hash))

    @input_timeout(BlockMetaDataRequest)
    def timeout_block_meta_request(self, request: BlockMetaDataRequest):
        self.log.error("BlockMetaDataRequest timed out!!!\nRequest={}".format(request))
        self._request_update()

    def _request_update(self):
        """
        Makes a BlockMetaDataRequest to a Masternode. This gives the delegate the block meta data for all new blocks
        that this delegate needs to fetch
        """
        self.parent.current_hash = BlockStorageDriver.get_latest_block_hash()

        self.log.notice("Requesting updates from Masternode with current block hash {}".format(self.parent.current_hash))
        request = BlockMetaDataRequest.create(current_block_hash=self.parent.current_hash)
        self.parent.composer.send_request_msg(message=request, vk=VKBook.get_masternodes()[0], timeout=BLOCK_REQ_TIMEOUT)

    def _update_next_block(self):
        """
        Pops a block meta off the queue (if we do not have a current one set), and requests that data for it
        """
        # If we are already working on a block meta, do nothing
        if self.current_block:
            return

        # If block queue is empty, request another update
        if len(self.new_blocks) == 0:
            self._request_update()
            return

        self.current_block = self.new_blocks.pop()
        self._fetch_tx_for_current_block()

    def _fetch_tx_for_current_block(self):
        """
        Fetches the transactions for the current block being updated
        """
        assert self.current_block, "_fetch_tx_for_current_block called but self.current_block not set!"

        request = TransactionRequest.create(self.current_block.merkle_leaves)
        self.parent.composer.send_request_msg(message=request, vk=VKBook.get_masternodes()[0])
        self.current_request = request
        # TODO implement request timeout functionality for TrnasactionRequest /w TX_REQ_TIMEOUT



