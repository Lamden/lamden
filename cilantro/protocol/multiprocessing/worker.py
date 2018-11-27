from cilantro.logger import get_logger
from cilantro.protocol import wallet
from cilantro.protocol.reactor.socket_manager import SocketManager

from typing import Callable
import zmq.asyncio, asyncio

import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


class Worker:

    def __init__(self, signing_key=None, loop=None, context=None, manager: SocketManager=None, name=''):
        name = name or type(self).__name__
        self.log = get_logger(name)

        if manager:
            assert not loop and not context and not signing_key, "If passing in a SocketManager you should omit all other args"
            signing_key, context, loop = manager.signing_key, manager.context, manager.loop
        else:
            assert signing_key, "Signing key arg is required if not passing in a SocketManager"
            if context: assert loop, 'If passing context, must also include loop'

        self.loop = loop or asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.context = context or zmq.asyncio.Context()

        self.signing_key = signing_key
        self.verifying_key = wallet.get_vk(self.signing_key)

        self.manager = manager or SocketManager(signing_key=signing_key, context=self.context, loop=self.loop)

    def add_overlay_handler_fn(self, key: str, handler: Callable[[dict], None]):
        """
        Adds a handler for a overlay events with name 'key'. Multiple handler events can be added for the same key,
        and all of them will be run in arbitrary order.
        :param key: The 'event' key of the overlay event which will trigger the callback handler
        :param handler: The function that is invoked once an overlay event is observed with the same event name as 'key'
        The handler function is called with a single arguement, a dictionary containing info about the overlay event
        """
        self.manager.overlay_callbacks[key].add(handler)
