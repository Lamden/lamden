from cilantro.protocol.reactor import ReactorInterface
from cilantro.protocol.statemachine import StateMachine
from cilantro.messages import ReactorCommand, Envelope, MessageMeta, Seal
from cilantro.protocol.reactor.executor import ROUTE_CALLBACK, ROUTE_REQ_CALLBACK, ROUTE_TIMEOUT_CALLBACK
from cilantro.logger import get_logger
"""
The Router class transports incoming data from the ReactorDaemon to the appropriate State Machine logic. It handles
signature checking   
"""


class Router:
    def __init__(self, statemachine):
        super().__init__()
        assert issubclass(type(statemachine), StateMachine), "Router must be created with a StateMachine instance"
        self.log = get_logger("Router")
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

        envelope, msg = None, None
        try:
            envelope = cmd.envelope
            if not envelope.verify_seal:
                self.log.error("\n\n\n Could not verify seal for envelope {} \n\n\n".format(envelope))
                return
            msg = envelope.message  # Ensure its possible to deserialize the data
        except Exception as e:
            self.log.error("\n\n!!!!!\nError unpacked cmd envelope {}\nCmd:\n{}\n!!!!\n".format(e, cmd))

        self.routes[cmd.callback](envelope)

    def _route(self, env: Envelope):
        """
        Routes an envelope to the appropriate @input receiver
        """
        self.log.debug("Routing envelope: {}".format(env))
        assert type(env.message) in self.sm.state._receivers, "State {} has no implemented receiver for {} in " \
                                                              "_receivers {}".format(self.sm.state, type(env.message),
                                                                                     self.sm.state._receivers)
        self.sm.state._receivers[type(env.messages)](self.sm.state, env.message)

    def _route_request(self, env: Envelope):
        """
        Routes a reply envelope to the appropriate @input receiver. This is different that a 'regular' (non request)
        envelope, because data returend to the @input function will be packaged as a reply and sent off to the daemon
        by the composer
        """
        self.log.debug("Routing request envelope: {}".format(env))

        # TODO -- make requests use the same decorator, @input, but allow them to return data which is packaged as a
        # reply. Thus this router instance would need access to the composer
        assert type(env.message) in self.sm.state._repliers, "No implemented replier"

    def _route_timeout(self, env: Envelope):
        """
        Routes a timed out request (that did not receive an associated reply in time)
        :param env:
        """
        self.log.debug("Routing timeout envelope: {}".format(env))
        assert type(env.message) in self.sm.state._timeouts, "No implemented handler for timeout message type {} in " \
                                                             "state {} with timeouts {}".format(type(env.message),
                                                              self.sm.state, self.sm.state._timeouts)

        self.sm.state._receivers[type(env.messages)](self.sm.state, env.message)
