from cilantro.logger import get_logger
from cilantro.protocol.transport import Composer
from cilantro.protocol.states.statemachine import StateMachine
from cilantro.protocol.multiprocessing.worker import Worker
from cilantro.protocol.overlay.daemon import OverlayServer
from cilantro.utils.lprocess import LProcess

import asyncio
import os
import time
from cilantro.protocol import wallet

# MANDATORY NAP TIME (How long each node sleeps after starting its overlay server)
# Technically, the system will work without this nap but allowing some padding time for dynamic discovery and such
# limits the number of re-auth attempts and lookup retries
BOOT_DELAY = 5


def take_a_nice_relaxing_nap(log):
    log.important("Taking a nice relaxing {} second nap while I wait for everybody to boot".format(BOOT_DELAY))
    time.sleep(BOOT_DELAY)
    log.important("Done with my boot nap. Time to get to get work.")


class NodeBase(StateMachine, Worker):

    def __init__(self, ip, signing_key, loop=None, name='Node'):
        self.log = get_logger(name)

        self.loop = loop or asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.log.notice("Starting overlay service")
        self.overlay_proc = LProcess(target=OverlayServer, kwargs={'sk': signing_key})
        self.overlay_proc.start()

        # TODO remove this once we implement a 'Staging' state for all nodes
        take_a_nice_relaxing_nap(self.log)

        # Init Super Classes (we had to start the Overlay Server first)
        Worker.__init__(self, signing_key=signing_key, loop=loop, name=name)

        StateMachine.__init__(self)

        self.ip = ip
        self.name = name

        self.log.important3("Node with vk {} has ip {}".format(self.verifying_key, ip))

        super().start()  # Start the state machine


class NewNodeBase(Worker):

    def __init__(self, ip, signing_key, loop=None, name='Node'):
        self.log = get_logger(name)
        self.ip = ip
        self.name = name

        self.loop = loop or asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.log.notice("Starting overlay service")
        self.overlay_proc = LProcess(target=OverlayServer, kwargs={'sk': signing_key})
        self.overlay_proc.start()  # TODO should we make this proc a daemon?

        # TODO remove this once we implement a 'Staging' state for all nodes
        take_a_nice_relaxing_nap(self.log)
        super().__init__(signing_key=signing_key, loop=loop, name=name)

        self.log.important3("Node with vk {} has ip {}".format(self.verifying_key, ip))

        # TODO wait for necessary num of nodes to come online
        # TODO run biz logic

