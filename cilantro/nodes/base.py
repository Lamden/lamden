from cilantro.logger import get_logger
from cilantro.protocol.transport import Composer
from cilantro.protocol.states.statemachine import StateMachine
import asyncio
# from cilantro.protocol.reactor.executor import *
from cilantro.protocol import wallet

class NodeBase(StateMachine):

    def __init__(self, ip, signing_key, loop, name='Node'):
        super().__init__()

        self.log = get_logger(name)
        self.ip = ip
        self.name = name

        self.signing_key = signing_key
        self.verifying_key = wallet.get_vk(self.signing_key)

        self.loop = loop
        asyncio.set_event_loop(loop)

        self._composer = None

        self.tasks = []

    def start(self, start_loop=True):
        """
        Kicks off the main event loop, and properly starts the Node. This call will block whatever thread its run on
        until the end of space and time (or until this Node/process is terminated)
        """
        assert self.composer, "Composer property must be set before start is called"

        # Start the state machine
        self.log.debug("Starting state machine")
        super().start()  # blocks until StateMachine finishes boot state

        # Start the main event loop
        self.log.debug("Starting ReactorInterface event loop")

        # ReactorInterface starts listening to messages from ReactorDaemon. Also starts any other tasks appended to
        # self.tasks by gathering them (using asyncio.gather) and then 'run_until_complete'-ing them in the event loop
        if start_loop:
            self.composer.interface.start_reactor(tasks=self.tasks)

    def teardown(self):
        """
        Tears down the application stack.
        """
        self.log.important("Tearing down application")
        self.composer.interface.teardown()
        # exit()

    @property
    def composer(self):
        return self._composer

    @composer.setter
    def composer(self, val):
        assert isinstance(val, Composer), ".composer property must be a Composer instance"
        assert self.composer is None, "Composer is already set (composer should only be set once during creation)"
        self._composer = val
