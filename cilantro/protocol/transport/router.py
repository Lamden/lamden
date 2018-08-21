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
    def __init__(self, get_handler_func, name='Node'):
        super().__init__()
        self.log = get_logger("{}.Router".format(name))
        self.get_handler_func = get_handler_func

        # Define mapping between callback names and router functions
        self.routes = {StateInput.INPUT: self._route,
                       StateInput.TIMEOUT: self._route,
                       StateInput.REQUEST: self._route_request,
                       StateInput.LOOKUP_FAILED: self._lookup_failed,
                       StateInput.SOCKET_CONNECTED: self._call_status_handler,
                       StateInput.CONN_DROPPED: self._call_status_handler}

    @property
    def handler(self):
        return self.get_handler_func()

    def route_callback(self, callback: str, *args, **kwargs):
        self.log.spam("Routing callback {} with\nargs={}\nkwargs={}".format(callback, args, kwargs))
        assert callback in self.routes, "Callback {} not found in route keys {}".format(callback, self.routes.keys())

        self.routes[callback](callback, *args, **kwargs)

    def _route(self, input_type, *args, **kwargs):
        """
        Should be for internal use only.
        Routes an envelope to the appropriate @input or @timeout receiver
        """
        self.handler.call_input_handler(input_type, *args, **kwargs)

    def _route_timeout(self, input_type, *args, **kwargs):
        self.handler.call_input_handler(StateInput.TIMEOUT, *args, **kwargs)

    def _route_request(self, input_type, *args, envelope=None, **kwargs):
        """
        Should be for internal use only.
        Routes a reply envelope to the appropriate @input receiver. This is different that a 'regular' (non request)
        envelope, because data returned to the @input function will be packaged as a reply and sent off by the composer
        """
        assert envelope, "_route_request was called with no envelope arg!"

        reply = self.handler.call_input_handler(input_type, *args, **kwargs)
        if not reply:
            self.log.debug("Warning -- No reply returned for request msg of type {}".format(type(envelope.message)))
            return

        assert isinstance(reply, MessageBase), "whatever is returned from @input_request function must be a " \
                                               "MessageBase subclass instance"

        self.log.spam("Sending reply message {}".format(reply))
        self.handler.composer.send_reply(message=reply, request_envelope=envelope)

    def _lookup_failed(self, input_type, *args, **kwargs):
        assert 'vk' in kwargs, "_lookup_failed route hit with no vk in kwargs...\nargs={}\nkwargs={}".format(args, kwargs)
        self.log.warning("Lookup failed for reactor command with vk {}. Retrying.".format(kwargs['vk']))

        # TODO set a max num retries, and propogate failure to SM handler if num retries is exceeded

        # self.handler.composer.interface.send_cmd(new_cmd)
        # TODO handle this ... retry it or route to input or something

    def _call_status_handler(self, input_type, *args, **kwargs):
        self.handler.call_status_input_handler(input_type=input_type, *args, **kwargs)
