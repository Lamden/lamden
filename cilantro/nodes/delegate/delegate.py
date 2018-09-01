"""
    Delegates

    Delegates are the "miners" of the Cilantro blockchain in that they opportunistically bundle up transaction into
    blocks and are rewarded with TAU for their actions. They receive approved transaction from TESTNET_DELEGATES and broadcast
    blocks based on a 1 second or 10,000 transaction limit per block. They should be able to connect/drop from the
    network seamlessly as well as coordinate blocks amongst themselves.

     Delegate logic:
        Step 1) Delegate takes 10k transaction from witness and forms a block
        Step 2) Block propagates across the network to other TESTNET_DELEGATES
        Step 3) Delegates pass around in memory DB hash to confirm they have the same blockchain state
        Step 4) Next block is mined and process repeats

        zmq pattern: subscribers (TESTNET_DELEGATES) need to be able to communicate with one another. this can be achieved via
        a push/pull pattern where all TESTNET_DELEGATES push their state to sink that pulls them in, but this is centralized.
        another option is to use ZMQ stream to have the tcp sockets talk to one another outside zmq
"""

from cilantro.nodes import NodeBase
from cilantro.storage.db import VKBook
from cilantro.storage.blocks import BlockStorageDriver

from cilantro.protocol.states.decorators import *
from cilantro.protocol.states.state import State
from cilantro.protocol.interpreter import SenecaInterpreter
from cilantro.utils.hasher import Hasher

from cilantro.messages.transaction.base import TransactionBase
from cilantro.messages.consensus.merkle_signature import MerkleSignature
from cilantro.messages.transaction.ordering import OrderingContainer
from cilantro.messages.block_data.transaction_data import TransactionReply, TransactionRequest
from cilantro.messages.envelope.envelope import Envelope
from cilantro.messages.block_data.block_metadata import BlockMetaDataReply, NewBlockNotification
from cilantro.messages.signals.kill_signal import KillSignal

from cilantro.constants.zmq_filters import DELEGATE_DELEGATE_FILTER, WITNESS_DELEGATE_FILTER, MASTERNODE_DELEGATE_FILTER
from cilantro.constants.delegate import BOOT_TIMEOUT, BOOT_REQUIRED_MASTERNODES, BOOT_REQUIRED_WITNESSES
from cilantro.constants.ports import MN_NEW_BLOCK_PUB_PORT

from collections import deque
from cilantro.protocol.structures.linked_hashtable import LinkedHashTable
import time

DelegateBootState = "DelegateBootState"
DelegateInterpretState = "DelegateInterpretState"
DelegateConsensusState = "DelegateConsensusState"
DelegateCatchupState = "DelegateCatchupState"


class Delegate(NodeBase):
    """
    Here we define 'global' properties shared among all Delegate states. Within a Delegate state, 'self.parent' refers
    to this instance.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Properties shared among all states (ie via self.parent.some_prop)
        self.pending_sigs, self.pending_txs = deque(), LinkedHashTable()
        self.interpreter = SenecaInterpreter()
        self.current_hash = BlockStorageDriver.get_latest_block_hash()


class DelegateBaseState(State):

    @input(KillSignal)
    def handle_kill_sig(self, msg: KillSignal):
        # TODO - make sure this is secure (from a legit Masternode)
        self.log.important("Node got received remote kill signal from network!")
        self.parent.teardown()

    def reset_attrs(self):
        pass

    @input_connection_dropped
    def conn_dropped(self, vk, ip):
        self.log.important2('({}:{}) has dropped'.format(vk, ip))
        pass

    @input(OrderingContainer)
    def handle_tx(self, tx: OrderingContainer):
        self.log.debugv("Delegate not interpreting transactions, adding {} to queue".format(tx))
        self.parent.pending_txs.append(Hasher.hash(tx.transaction), tx)
        self.log.debugv("{} transactions pending interpretation".format(len(self.parent.pending_txs)))

    @input(MerkleSignature)
    def handle_sig(self, sig: MerkleSignature):
        self.log.info("Received signature with data {} but not in consensus, adding it to queue"
                       .format(sig._data))
        self.parent.pending_sigs.append(sig)

    @input(NewBlockNotification)
    def handle_new_block_notif(self, notif: NewBlockNotification):
        self.log.critical("Delegate got new block notification with hash {}\nprev_hash {}]\nand our current hash = {}"
                          .format(notif.block_hash, notif.prev_block_hash, self.parent.current_hash))
        self.parent.transition(DelegateCatchupState)

    @input(TransactionReply)
    def handle_tx_reply(self, reply: TransactionReply, envelope: Envelope):
        self.log.warning("Delegate current state {} not configured to handle"
                       "transaction replies".format(self))

    @input_request(TransactionRequest)
    def handle_tx_request(self, request: TransactionRequest):
        self.log.warning("Delegate current state {} not configured to handle"
                        "transaction requests".format(self))

    @input(BlockMetaDataReply)
    def handle_blockmeta_reply(self, reply: BlockMetaDataReply):
        self.log.warning("Delegate current state {} not configured to handle block"
                       "meta replies".format(self))


@Delegate.register_init_state
class DelegateBootState(DelegateBaseState):
    """
    Delegate Boot State consists of subscribing to all TESTNET_DELEGATES/all TESTNET_WITNESSES as well as publishing to own url
    Also the delegate adds a router and dealer socket so masternode can identify which delegate is communicating
    """

    def reset_attrs(self):
        self.connected_masternodes = set()
        self.connected_delegates = set()
        self.connected_witnesses = set()

    @timeout_after(BOOT_TIMEOUT)
    def timeout(self):
        self.log.fatal("Delegate failed to connect to required nodes during boot state! Exiting system.")
        self.log.fatal("Connected Masternodes: {}".format(self.connected_masternodes))
        self.log.fatal("Connected Delegates: {}".format(self.connected_delegates))
        self.log.fatal("Connected Witnesses: {}".format(self.connected_witnesses))
        exit()

    @input_socket_connected
    def socket_connected(self, socket_type: int, vk: str, url: str):
        assert vk in VKBook.get_all(), "Connected to vk {} that is not present in VKBook.get_all()!!!".format(vk)
        key = vk + '_' + str(socket_type)
        self.log.spam("Delegate connected to vk {} with sock type {}".format(vk, socket_type))

        # TODO make less ugly pls
        if vk in VKBook.get_delegates():
            self.connected_delegates.add(key)
        elif vk in VKBook.get_masternodes():
            self.connected_masternodes.add(key)
        elif vk in VKBook.get_witnesses():
            self.connected_witnesses.add(key)

        self._check_ready()

    @enter_from_any
    def enter_any(self, prev_state):
        self.reset_attrs()

        self.log.notice("Delegate connecting to other nodes ..")
        # Sub to other delegates
        for delegate_vk in VKBook.get_delegates():
            if delegate_vk == self.parent.verifying_key:  # Do not sub to yourself
                continue

            self.parent.composer.add_sub(vk=delegate_vk, filter=DELEGATE_DELEGATE_FILTER)

        # Sub to witnesses
        for witness_vk in VKBook.get_witnesses():
            self.parent.composer.add_sub(vk=witness_vk, filter=WITNESS_DELEGATE_FILTER)

        # Pub on our own url
        self.parent.composer.add_pub(ip=self.parent.ip)

        # Add router socket
        self.parent.composer.add_router(ip=self.parent.ip)

        # Add dealer and sub socket for Masternodes
        for mn_vk in VKBook.get_masternodes():
            self.parent.composer.add_dealer(vk=mn_vk)
            self.parent.composer.add_sub(vk=mn_vk, filter=MASTERNODE_DELEGATE_FILTER, port=MN_NEW_BLOCK_PUB_PORT)

    def _check_ready(self):
        """
        Checks if the Delegate has connected to a sufficient number of other nodes. If all criteria are met, this method
        will transition into DelegateCatchupState. If any criteria is not met, this method returns and does nothing
        """
        # Note: We multiply BOOT_REQUIRED_MASTERNODES by 2 because we expected 2 sockets to be added for each MN
        # (1 dealer socket, 1 subscriber socket)
        if (len(self.connected_masternodes) < BOOT_REQUIRED_MASTERNODES * 2) or \
                (len(self.connected_witnesses) < BOOT_REQUIRED_WITNESSES) or \
                (len(self.connected_delegates) < VKBook.get_delegate_majority()):
            return

        self.log.important("Delegate connected to sufficient nodes! Transitioning to CatchupState")
        self.parent.transition(DelegateCatchupState)


