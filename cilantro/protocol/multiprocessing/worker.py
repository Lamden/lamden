from cilantro.logger import get_logger
from cilantro.protocol import wallet
from cilantro.protocol.reactor.socket_manager import SocketManager
from cilantro.messages.envelope.envelope import Envelope

from typing import Callable, Union
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

    def open_envelope(self, env_bytes: bytes, validate=True, sender_groups: Union[tuple, str]=None) -> Union[Envelope, bool]:
        """
        Attempts to deserialize an envelope, returning False if an error occurs or if the envelope is not from a valid
        sender. 'sender_groups' can be passed in to also verify that the envelope was from an appropriate node type
        (ie to check if this envelope was indeed from a masternode/witness/delegate)
        :param env_bytes: A serialized envelope, in bytes
        :param validate: If true validate the envelope (ie check seal, make sure meta/message deserialize, ect)
        :param sender_groups: A str, representing a type from enum NodeTypes, or a list of a said strings
        :return: The deserialized envelope if all validation passes, or False if it does not
        """
        try:
            env = Envelope.from_bytes(env_bytes, validate=validate)
        except Exception as e:
            self.log.warning("Error deserializing/validating envelope! Error: {}\nEnvelope binary: {}".format(e, env_bytes))
            return False

        if sender_groups and not env.is_from_group(sender_groups):
            self.log.warning("Could not verify sender is from group(s) <{}> for envelope {}".format(sender_groups, env))
            return False

        # If we did not validate it, still check the seal
        if not validate and not env.verify_seal:
            self.log.warning("Could not verify seal on envelope! Envelope: {}".format(env))
            return False

        return env
