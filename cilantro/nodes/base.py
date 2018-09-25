from cilantro.logger import get_logger
from cilantro.protocol.transport import Composer
from cilantro.protocol.states.statemachine import StateMachine
from cilantro.protocol.multiprocessing.worker import Worker
from cilantro.protocol.overlay.interface import OverlayServer, OverlayClient
from cilantro.utils.lprocess import LProcess

import asyncio
import os
import time
from cilantro.protocol import wallet


BOOT_DELAY = 16  # MANDATORY NAP TIME (How long each node sleeps after starting its overlay server)

def take_a_nice_relaxing_nap(log):
    log.important("Taking a nice relaxing {} second nap while I wait for everybody to boot".format(BOOT_DELAY))
    time.sleep(BOOT_DELAY)
    log.important("Done with my boot nap. Time to get to get work.")


class NewNodeBase(StateMachine, Worker):

    def __init__(self, ip, signing_key, loop=None, name='Node'):
        self.log = get_logger(name)

        self.loop = loop or asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.log.notice("Starting overlay service")
        self.overlay_proc = LProcess(target=OverlayServer, kwargs={'sk': signing_key})
        self.overlay_proc.start()

        # TODO remove this once we implement a 'Staging' state for all nodes
        take_a_nice_relaxing_nap(self.log)

        # TODO -- block here until the OverlayServer is ready. That way Workers never have to wait

        # Init Super Classes (we had to start the Overlay Server first)

        self.log.important3("NewNodeBase instantiating Worker superclass! (blocking call)")
        Worker.__init__(self, signing_key=signing_key, loop=loop, name=name)
        self.log.important3("NewNodeBase finished instantiating Worker superclass.")

        StateMachine.__init__(self)

        self.ip = ip
        self.name = name

        self.log.important3("Node with vk {} has ip {}".format(self.verifying_key, ip))

        super().start()  # Start the state machine


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
        self.overlay_proc = LProcess(target=OverlayServer, kwargs={'sk':signing_key})
        self.overlay_proc.start()

        # TODO remove this once we implement a 'Staging' state for all nodes
        take_a_nice_relaxing_nap(self.log)

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
