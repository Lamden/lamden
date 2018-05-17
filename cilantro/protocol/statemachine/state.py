from cilantro.logger import get_logger
from functools import wraps
from cilantro.messages import MessageBase, Envelope
from cilantro.protocol.statemachine.decorators import StateInput
import inspect

_ENTER, _EXIT, _RUN = 'enter', 'exit', 'run'
_DEBUG_FUNCS = (_ENTER, _EXIT, _RUN)


def debug_transition(transition_type):
    """
    Decorator to magically log any transitions on StateMachines
    """
    def decorate(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_state = args[0]
            if transition_type == _RUN:
                msg = "Running state {}".format(current_state)
            else:
                trans_state = args[1]
                msg = "Entering state {} from previous state {}" if transition_type == _ENTER \
                    else "Exiting state {} to next state {}"
                msg = msg.format(current_state, trans_state)

                other_args = args[2:]
                if len(other_args) > 0 or len(kwargs) > 0:
                    msg += "... with additional args = {}, kwargs = {}".format(other_args, kwargs)

            current_state.log.info(msg)
            return func(*args, **kwargs)
        return wrapper
    return decorate


class StateMeta(type):
    """
    Metaclass to register state receivers.
    """
    def __new__(cls, clsname, bases, clsdict):
        clsobj = super().__new__(cls, clsname, bases, clsdict)
        clsobj.log = get_logger(clsname)

        # Add debug decorator to run/exit/enter methods
        for name, val in vars(clsobj).items():
            if callable(val) and name in _DEBUG_FUNCS:
                # print("Setting up debug logging for name {} with val {}".format(name, val))
                setattr(clsobj, name, debug_transition(name)(val))

        # Configure receivers, repliers, and timeouts
        for input_type in StateInput.ALL:
            setattr(clsobj, input_type, {})

            # Populate receivers s.t. all subclass receivers are inherited unless this class implements its own version
            for r in dir(clsobj):
                func = getattr(clsobj, r)

                if hasattr(func, input_type):
                    func_input_type = getattr(func, input_type)
                    registry = getattr(clsobj, input_type)

                    registry[func_input_type] = func

                    for sub in filter(lambda k: k not in registry, StateMeta._get_subclasses(func_input_type)):
                        registry[sub] = func

        return clsobj

    @staticmethod
    def _get_subclasses(obj_cls, subs=None) -> list:
        if subs is None:
            subs = []

        new_subs = obj_cls.__subclasses__()
        subs.extend(new_subs)
        for sub in new_subs:
            subs.extend(StateMeta._get_subclasses(sub, subs=subs))

        return subs


class State(metaclass=StateMeta):
    def __init__(self, state_machine):
        self.parent = state_machine
        self.reset_attrs()

    def reset_attrs(self):
        pass

    def enter(self, prev_state, *args, **kwargs):
        pass

    def exit(self, next_state, *args, **kwargs):
        pass

    def run(self):
        pass

    def call_input_handler(self, message, input_type: str, envelope=None):
        # TODO assert type message is MessageBase, and envelope is Envelope ???
        self._assert_has_input_handler(message, input_type)

        func = self._get_input_handler(message, input_type)

        if self._has_envelope_arg(func):
            self.log.debug("ENVELOPE DETECTED IN HANDLER ARGS")  # todo remove this
            output = func(self, message, envelope=envelope)
        else:
            output = func(self, message)

        return output

    def _get_input_handler(self, message, input_type: str):
        registry = getattr(self, input_type)
        assert isinstance(registry, dict), "Expected registry to be a dictionary!"

        func = registry[type(message)]
        return func

    def _has_envelope_arg(self, func):
        # TODO more robust logic that searches through parameter type annotations one that is typed with Envelope class
        sig = inspect.signature(func)
        return 'envelope' in sig.parameters

    def _assert_has_input_handler(self, message: MessageBase, input_type: str):
        # Assert that input_type is actually a recognized input_type
        assert input_type in StateInput.ALL, "Input type {} not found in StateInputs {}"\
                                             .format(input_type, StateInput.ALL)

        # Assert that this state, or one of its superclasses, has an appropriate receiver implemented
        assert type(message) in getattr(self, input_type), \
            "No handler for message type {} found in handlers for input type {} which has handlers: {}"\
            .format(type(message), input_type, getattr(self, input_type))

    def __eq__(self, other):
        return type(self) == type(other)

    def __repr__(self):
        return type(self).__name__


class EmptyState(State):
    def enter(self, prev_state): pass
    def exit(self, next_state): pass
    def run(self): pass
