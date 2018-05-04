from cilantro import Constants
from cilantro.logger import get_logger
from cilantro.protocol.transport import Composer
from cilantro.protocol.statemachine import StateMachine
# from cilantro.protocol.reactor.executor import *


class NodeBase(StateMachine):

    def __init__(self, url, signing_key, loop):
        super().__init__()

        self.log = get_logger(type(self).__name__)

        self.url = url
        self.signing_key = signing_key

        self.loop = loop
        self._composer = None

        self.nodes_registry = Constants.Testnet.AllNodes  # TODO move away from this once we get dat good overlay net

    def start(self):
        """
        Kicks off the main event loop, and properly starts the Node. This call will block whatever thread its run on
        until the end of space and time (or until this Node/process is terminated)
        """
        assert self.composer, "Composer property must be set before start is called"

        # Start the state machine
        self.log.critical("Starting state machine")
        super().start()  # blocks until StateMachine finishes boot state

        # Start the main event loop
        self.log.critical("Starting ReactorInterface event loop")
        self.composer.interface.start_reactor()  # ReactorInterface starts listening to messages from ReactorDaemon

    @property
    def composer(self):
        return self._composer

    @composer.setter
    def composer(self, val):
        print("\n\n\n SETTING COMPOSER TO VAL: {}\n\n\n".format(val))
        assert isinstance(val, Composer), ".composer property must be a Composer instance"
        assert self.composer is None, "Composer is already set (composer should only be set once during creation)"
        self._composer = val





