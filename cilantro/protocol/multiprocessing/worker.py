import asyncio, os
import zmq.asyncio

from cilantro.logger import get_logger
from cilantro.protocol import wallet
from cilantro.protocol.reactor.executor import Executor
from cilantro.protocol.reactor.manager import ExecutorManager
from cilantro.protocol.transport.router import Router
from cilantro.protocol.transport.composer import Composer
from cilantro.protocol.states.state import State

import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


class Worker(State):  # or should this be called 'WorkerProcess' ... or something else entirely? tbd, stay tuned in to find out

    def setup(self):
        """
        This method is run when the object is instantiated, just before the event loop is started. Any constructor code,
        (which traditionally would be put in __init__) should be done here. All key word arguments passed into the
        __init__ function are available as instance variables here.
        """
        pass

    def __init__(self, ip: str, signing_key: str, name=None, *args, **kwargs):
        """
        IMPORTANT: This should not be overridden by subclasses. Instead, override the setup() method.

        Creates a Worker instance and starts the event loop. Instantiating this class blocks indefinitely, thus any
        setup must be done by overriding the setup() method (see comments below for explanation)
        :param args: This should never be set, as only kwargs are supported.
        :param kwargs: A list of named variables that will be set as instance attributes.
        """
        assert len(args) == 0, "Worker cannot be constructed with args. Only key word args are supported."

        name = name or type(self).__name__
        self.name = name
        self.signing_key = signing_key
        self.ip = ip
        self.verifying_key = wallet.get_vk(self.signing_key)
        self.log = get_logger(name)

        # We set all kwargs to instance variables so they are accessible in the setup() function. Setup cannot be done
        # in subclasses by overriding __init__ because instantiating this instance involves running an event loop
        # forever (which would block the setup code upon calling 'super().__init__(..)' in the subclass)
        # TODO this pattern is questionable. Perhaps args/kwargs should be passed into setup(...)?  --davis
        for k, v in kwargs.items():
            setattr(self, k, v)

        self._router = Router(get_handler_func=lambda: self, name=name)
        self._manager = ExecutorManager(signing_key=signing_key, router=self._router, name=name)
        self.composer = Composer(manager=self._manager, signing_key=signing_key, ip=ip, name=name)
        self._router.composer = self.composer

        self.setup()

        self.log.notice("Starting Worker named {}".format(name))
        self._manager.start()  # This starts the event loop and blocks this process indefinitely

