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

from cilantro.nodes.base import NewNodeBase
from cilantro.nodes.delegate.block_manager import BlockManager
from cilantro.storage.db import VKBook

from cilantro.protocol.states.decorators import *
from cilantro.protocol.states.state import State
from cilantro.utils.lprocess import LProcess

from cilantro.constants.delegate import BOOT_TIMEOUT, BOOT_REQUIRED_MASTERNODES, BOOT_REQUIRED_WITNESSES


DelegateBootState = "DelegateBootState"
DelegateInterpretState = "DelegateInterpretState"
DelegateConsensusState = "DelegateConsensusState"
DelegateCatchupState = "DelegateCatchupState"


class Delegate(NewNodeBase):
    """
    Here we define 'global' properties shared among all Delegate states. Within a Delegate state, 'self.parent' refers
    to this instance.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Properties shared among all states (ie via self.parent.some_prop)


class DelegateBaseState(State):
    pass


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

        self.parent.transition(DelegateRunState)

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
        self.parent.transition(DelegateRunState)


@Delegate.register_state
class DelegateRunState(DelegateBaseState):

    def reset_attrs(self):
        pass

    @enter_from_any
    def enter_any(self):
        # Start the BlockManager. Instantiating this object starts an event loop and blocks

        # (ip=self.parent.ip, signing_key=self.parent.signing_key)
        self.log.notice("Delegate Starting BlockManager Process")
        self.bm_proc = LProcess(target=BlockManager, kwargs={'ip': self.parent.ip, 'signing_key':self.parent.signing_key})
        self.bm_proc.start()



