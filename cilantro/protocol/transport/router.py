import inspect
from cilantro.protocol.states.statemachine import StateMachine
from cilantro.protocol.states.state import StateInput
from cilantro.messages.reactor.reactor_command import ReactorCommand
from cilantro.messages.base.base import MessageBase
from cilantro.logger import get_logger


class Router:
    """
    The Router class transports incoming data from the ReactorDaemon to the appropriate State Machine logic.
    """
    def __init__(self, statemachine: StateMachine, name='Node'):
        super().__init__()
        self.log = get_logger("{}.Router".format(name))
        self.sm = statemachine

        # Define mapping between callback names and router functions
        self.routes = {StateInput.INPUT: self._route,
                       StateInput.REQUEST: self._route_request,
                       StateInput.TIMEOUT: self._route,
                       StateInput.LOOKUP_FAILED: self._lookup_failed,
                       StateInput.SOCKET_CONNECTED: self._socket_connected,
                       StateInput.CONN_DROPPED: self._connection_dropped}

    def route_callback(self, cmd: ReactorCommand):
        """
        Takes in a callback from a ReactorInterface, and invokes the appropriate receiver on the state machine
        """
        self.log.spam("ROUTING CALLBACK:\n{}".format(cmd))
        assert isinstance(cmd, ReactorCommand), "route_callback must take a ReactorCommand instance as input"
        assert cmd.callback, "ReactorCommand {} does not have 'callback' in kwargs".format(cmd)
        assert cmd.callback in self.routes, "Unrecognized callback {}".format(cmd.callback)

        # TODO remove below (this is just debug checking)
        # Super extra sanity check to make sure id frame from requests matches seal's vk (this is also done in Daemon)
        if cmd.callback == StateInput.REQUEST:
            assert cmd.kwargs['header'] == cmd.envelope.seal.verifying_key, "Header frame and VK dont match!!!"
            assert cmd.envelope.verify_seal(), "Envelope couldnt be verified! This should of been checked " \
                                               "by the ReactorDaemon!!!!"

        if cmd.envelope:
            envelope = None
            try:
                envelope = cmd.envelope
                if not envelope.verify_seal():
                    self.log.error("\n\n\n Could not verify seal for envelope {} \n\n\n".format(envelope))
                    return
                # Ensure its possible to deserialize the data (this will raise exception if not)
                # Deserializing the data (via from_bytes(..) also runs .validate() on the message)
                msg = envelope.message
            except Exception as e:
                self.log.error("\n\n!!!!!\nError unpacking cmd envelope {}\nCmd:\n{}\n!!!!\n".format(e, cmd))
                return

        # Route command to subroutine based on callback
        self.routes[cmd.callback](cmd)

    def _route(self, cmd: ReactorCommand):
        """
        Should be for internal use only.
        Routes an envelope to the appropriate @input or @timeout receiver
        """
        self.sm.state.call_input_handler(cmd.envelope.message, cmd.callback, envelope=cmd.envelope)

    def _route_request(self, cmd: ReactorCommand):
        """
        Should be for internal use only.
        Routes a reply envelope to the appropriate @input receiver. This is different that a 'regular' (non request)
        envelope, because data returned to the @input function will be packaged as a reply and sent off to the daemon
        by the composer
        """
        reply = self.sm.state.call_input_handler(cmd.envelope.message, cmd.callback, envelope=cmd.envelope)

        if not reply:
            self.log.debug("Warning -- No reply returned for request msg of type {}".format(type(cmd.envelope.message)))
            return

        assert isinstance(reply, MessageBase), "whatever is returned from @input_request function must be a " \
                                               "MessageBase subclass instance"

        self.log.spam("Sending reply message {}".format(reply))
        self.sm.composer.send_reply(message=reply, request_envelope=cmd.envelope)

    def _lookup_failed(self, cmd: ReactorCommand):
        # TODO set a max num retries, and propogate failure to SM handler if num retries is exceeded

        kwargs = cmd.kwargs
        self.log.warning("Lookup failed for reactor command with vk {}. Retrying.".format(kwargs['vk']))

        del(kwargs['callback'])
        new_cmd = ReactorCommand.create_cmd(envelope=cmd.envelope, **kwargs)
        self.sm.composer.interface.send_cmd(new_cmd)

    def _socket_connected(self, cmd: ReactorCommand):
        # self.log.spam("Socket Connected! Router got cmd {}".format(cmd))  # TODO remove this (debug line)
        kwargs = cmd.kwargs
        del(kwargs['callback'])
        self.sm.state.call_status_input_handler(input_type=StateInput.SOCKET_CONNECTED, **kwargs)

    def _connection_dropped(self, cmd: ReactorCommand):
        kwargs = cmd.kwargs
        del(kwargs['callback'])
        self.sm.state.call_status_input_handler(input_type=StateInput.CONN_DROPPED, **kwargs)
