import inspect
from cilantro.protocol.statemachine import StateMachine, StateInput, State
from cilantro.messages import ReactorCommand, Envelope, MessageMeta, Seal, MessageBase
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
                       StateInput.LOOKUP_FAILED: self._lookup_failed}

    def route_callback(self, cmd: ReactorCommand):
        """
        Takes in a callback from a ReactorInterface, and invokes the appropriate receiver on the state machine
        """
        self.log.debug("ROUTING CALLBACK:\n{}".format(cmd))
        assert isinstance(cmd, ReactorCommand), "route_callback must take a ReactorCommand instance as input"
        assert cmd.callback, "ReactorCommand {} does not have 'callback' in kwargs"
        assert cmd.callback in self.routes, "Unrecognized callback name"

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
            self.log.warning("No reply returned for request msg of type {}".format(type(cmd.envelope.message)))
            return

        assert isinstance(reply, MessageBase), "whatever is returned from @input_request function must be a " \
                                               "MessageBase subclass instance"

        self.log.debug("Sending reply message {}".format(reply))
        self.sm.composer.send_reply(message=reply, request_envelope=cmd.envelope)

    def _lookup_failed(self, cmd: ReactorCommand):

        kwargs = cmd.kwargs
        del(kwargs['callback'])
        new_cmd = ReactorCommand.create_cmd(envelope=cmd.envelope, **kwargs)

        import time
        time.sleep(0.5)

        self.sm.composer.interface.send_cmd(new_cmd)
