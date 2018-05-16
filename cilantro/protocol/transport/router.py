import inspect
from cilantro.protocol.statemachine import StateMachine
from cilantro.messages import ReactorCommand, Envelope, MessageMeta, Seal, MessageBase
from cilantro.protocol.reactor.executor import ROUTE_CALLBACK, ROUTE_REQ_CALLBACK, ROUTE_TIMEOUT_CALLBACK
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
        self.routes = {ROUTE_CALLBACK: self._route,
                       ROUTE_REQ_CALLBACK: self._route_request,
                       ROUTE_TIMEOUT_CALLBACK: self._route_timeout}

    def route_callback(self, cmd: ReactorCommand):
        """
        Takes in a callback from a ReactorInterface, and invokes the appropriate receiver on the state machine
        """
        self.log.debug("ROUTING CALLBACK:\n{}".format(cmd))
        assert isinstance(cmd, ReactorCommand), "route_callback must take a ReactorCommand instance as input"
        assert cmd.callback, "ReactorCommand {} does not have 'callback' in kwargs"
        assert cmd.callback in self.routes, "Unrecognized callback name"

        # TODO remove below (this is just debug checking)
        # Super extra sanity check to make sure id frame from requests matches seal's vk
        if cmd.callback == ROUTE_REQ_CALLBACK:
            assert cmd.kwargs['header'] == cmd.envelope.seal.verifying_key, "Header frame and VK dont match!!!"
            assert cmd.envelope.verify_seal(), "Envelope couldnt be verified! This should of been checked " \
                                               "by the ReactorDaemon!!!!"

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

        # Assert state machine has an implemented handler for the message type and callback, then actually route it
        self._assert_handler_exists(type(envelope.message), cmd.callback)
        self.routes[cmd.callback](envelope)

    def _route(self, env: Envelope):
        """
        Should be for internal use only.
        Routes an envelope to the appropriate @input receiver
        """
        self.log.debug("Routing envelope: {}".format(env))

        handler_fn = self.sm.state._receivers[type(env.message)]
        sig = inspect.signature(handler_fn)
        self.log.critical("handler_fn {} has signature {}".format(handler_fn, sig))

        if 'envelope' in sig.parameters:
            self.log.critical("\n\nENVELOPE DETECTED IN HANDLER!!!\n\n")
            self.sm.state._receivers[type(env.message)](self.sm.state, env.message, envelope=env)
        else:
            self.sm.state._receivers[type(env.message)](self.sm.state, env.message)

    def _route_request(self, env: Envelope):
        """
        Should be for internal use only.
        Routes a reply envelope to the appropriate @input receiver. This is different that a 'regular' (non request)
        envelope, because data returned to the @input function will be packaged as a reply and sent off to the daemon
        by the composer
        """
        self.log.debug("Routing REQUEST envelope: {}".format(env))

        self.log.critical("sending request to handler")
        reply = self.sm.state._repliers[type(env.message)](self.sm.state, env.message)
        self.log.critical("got reply envelope from handler")

        if not reply:
            self.log.warning("No reply returned for request msg of type {}".format(type(env.message)))
            return

        assert isinstance(reply, MessageBase), "whatever is returned from @input_request function must be a " \
                                               "MessageBase subclass instance"

        self.sm.composer.send_reply(message=reply, request_envelope=env)

    def _route_timeout(self, env: Envelope):
        """
        Should be for internal use only.
        Routes a timed out request (that did not receive an associated reply in time)
        :param env:
        """
        # TODO -- implement this correctly
        self.log.debug("Routing timeout envelope: {}".format(env))
        assert type(env.message) in self.sm.state._timeouts, "No implemented handler for timeout message type {} in " \
                                                             "state {} with timeouts {}".format(type(env.message),
                                                              self.sm.state, self.sm.state._timeouts)

        self.sm.state._receivers[type(env.messages)](self.sm.state, env.message)

    def _assert_handler_exists(self, msg_type, callback):
        """
        Helper method to check if current state has a handler (a @input(msg_type) func) for msg_type. Raises an
        assertion if it doesnt.
        :param msg_type: A MessageBase class (not an instance but the actual Class of that instance)
        """
        # Define a mapping between routes and handlers
        handlers = {ROUTE_CALLBACK: self.sm.state._receivers, ROUTE_REQ_CALLBACK: self.sm.state._repliers,
                         ROUTE_TIMEOUT_CALLBACK: self.sm.state._repliers}
        assert callback in handlers, "Callback {} was not in self.routes {}".format(callback, handlers)

        search_scope = handlers[callback]
        assert msg_type in search_scope, "State {} has no implemented receiver for {} with callback {} in " \
                                                              "_receivers {}".format(self.sm.state, msg_type, callback,
                                                                                     search_scope)
