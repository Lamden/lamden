from cilantro.logger import get_logger
from cilantro.protocol.transport import Composer
from cilantro.protocol.states.statemachine import StateMachine
from cilantro.protocol.overlay.interface import OverlayInterface
from cilantro.utils.lprocess import LProcess

import asyncio
import os
from cilantro.protocol import wallet

class NodeBase(StateMachine):

    def __init__(self, ip, signing_key, loop, name='Node'):
        super().__init__()

        self.log = get_logger(name)
        self.ip = ip
        self.name = name

        self.signing_key = signing_key
        self.verifying_key = wallet.get_vk(self.signing_key)

        self.log.important3("Node with vk {} has ip {}".format(self.verifying_key, os.getenv("HOST_IP")))

        self.loop = loop
        asyncio.set_event_loop(loop)

        self.log.notice("Starting overlay service")
        self.overlay_proc = LProcess(target=OverlayInterface.start_service, args=(signing_key,))
        self.overlay_proc.start()

        self._composer = None

        self.tasks = []

    def start(self, start_loop=True):
        """
        Kicks off the main event loop, and properly starts the Node. This call will block whatever thread its run on
        until the end of space and time (or until this Node/process is terminated)
        """
        assert self.composer, "Composer property must be set before start is called"

        # Start the state machine
        self.log.info("Bootstrapping state machine into initial state")
        super().start()  # blocks until StateMachine finishes boot state

        # Start all futures ... # TODO we should probly wrap each in a try/catch so the exceptions arent swallowed up
        for future in self.tasks:
            asyncio.ensure_future(future)

        if start_loop:
            self.composer.manager.start()

    def teardown(self):
        """
        Tears down the application stack.
        """
        self.log.important("Tearing down application")
        self.composer.interface.teardown()
        if hasattr(self, 'server'):
            self.server.terminate()

    @property
    def composer(self):
        return self._composer

    @composer.setter
    def composer(self, val):
        assert isinstance(val, Composer), ".composer property must be a Composer instance"
        assert self.composer is None, "Composer is already set (composer should only be set once during creation)"
        self._composer = val
