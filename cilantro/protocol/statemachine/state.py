from cilantro.logger import get_logger
from functools import wraps
from cilantro.messages import MessageBase, Envelope
from cilantro.protocol.statemachine.decorators import StateInput, StateTimeout, StateTransition, exit_to_any
import inspect
from collections import defaultdict
from unittest.mock import MagicMock

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
        # StateMeta._config_debugging(clsobj)

        # Configure receivers, repliers, and timeouts
        StateMeta._config_input_handlers(clsobj)

        # Configure entry and exit handlers
        StateMeta._config_transitions(clsobj)

        # Configure State timeout timer
        StateMeta._config_state_timeout(clsobj)

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

    @staticmethod
    def _config_transitions(clsobj):
        for trans_attr in (StateTransition.ENTER, StateTransition.EXIT):
            setattr(clsobj, trans_attr, {})
            setattr(clsobj, StateTransition.get_any_attr(trans_attr), None)

            vars_copy = vars(clsobj)
            for r in vars_copy:
                func = getattr(clsobj, r)

                if hasattr(func, trans_attr):
                    states = getattr(func, trans_attr)

                    if states == StateTransition.ACCEPT_ALL:

                        any_attr_val = getattr(clsobj, StateTransition.get_any_attr(trans_attr))
                        # If we already set this value to the same func before, then ignore
                        if any_attr_val == func:
                            # print("\n\n any recevier already set; skipping it\n\n")
                            continue

                        # Sanity check to make sure this class doesnt have a any transition decorator already applied
                        assert any_attr_val is None, "ANY transition {} decorator already set to {} for class {}! " \
                                                     "(attempted to set it again to func: {})"\
                                                     # .format(trans_attr, any_attr_val, clsobj, func)

                        setattr(clsobj, StateTransition.get_any_attr(trans_attr), func)
                    else:
                        trans_registry = getattr(clsobj, trans_attr)
                        for state in states:
                            # Sanity check to make sure another handler is not already defined for this state
                            assert state not in trans_registry, "{} transition decorator already defined for State {}" \
                                                                " with transition registry {} .. (dupe = {})"\
                                                                .format(trans_attr, state, trans_registry, state)
                            trans_registry[state] = func

    @staticmethod
    def _config_debugging(clsobj):
        for name, val in vars(clsobj).items():
            if callable(val) and name in _DEBUG_FUNCS:
                # print("Setting up debug logging for name {} with val {}".format(name, val))
                setattr(clsobj, name, debug_transition(name)(val))

    @staticmethod
    def _config_input_handlers(clsobj):
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

    @staticmethod
    def _config_state_timeout(clsobj):
        setattr(clsobj, StateTimeout.TIMEOUT_FLAG, None)
        setattr(clsobj, StateTimeout.TIMEOUT_DUR, None)

        vars_copy = vars(clsobj)
        for r in vars_copy:
            func = getattr(clsobj, r)

            if hasattr(func, StateTimeout.TIMEOUT_FLAG):
                assert getattr(clsobj, StateTimeout.TIMEOUT_FLAG) is None, \
                    "State timeout already set to {}. Attempted to reset it to {}"\
                    .format(getattr(clsobj, StateTimeout.TIMEOUT_FLAG), func)
                assert hasattr(func, StateTimeout.TIMEOUT_DUR), "StateMeta Error! Function has no timeout duration attr"

                setattr(clsobj, StateTimeout.TIMEOUT_FLAG, func)
                setattr(clsobj, StateTimeout.TIMEOUT_DUR, getattr(func, StateTimeout.TIMEOUT_DUR))

                return


class State(metaclass=StateMeta):
    def __init__(self, state_machine):
        self.parent = state_machine
        self.reset_attrs()

    def reset_attrs(self):
        raise NotImplementedError("reset_attrs must be implemented for any State subclass")

    def call_input_handler(self, message, input_type: str, envelope=None):
        # TODO assert type message is MessageBase, and envelope is Envelope ???
        self._assert_has_input_handler(message, input_type)

        func = self._get_input_handler(message, input_type)

        # TODO -- find cleaner way to copy method signatures in unit tests
        if (isinstance(func, MagicMock) and envelope) or self._has_envelope_arg(func):
            assert envelope, "Envelope arg was found for input func {}, " \
                             "but no envelope passed into call_input_handler".format(func)
            self.log.debug("ENVELOPE DETECTED IN HANDLER ARGS")  # todo remove this
            output = func(message, envelope=envelope)
        else:
            output = func(message)

        return output

    def call_transition_handler(self, trans_type, state, *args, **kwargs):
        trans_func = self._get_transition_handler(trans_type, state)

        if not trans_func:
            return

        timeout_func = getattr(self, StateTimeout.TIMEOUT_FLAG)

        if trans_type == StateTransition.ENTER:
            # Check for timeout trigger
            if timeout_func:
                timeout_dur = getattr(self, StateTimeout.TIMEOUT_DUR)

                self.log.debug("Scheduling timeout trigger {} after {} seconds".format(timeout_func, timeout_dur))
                self.timeout_handler = self.parent.loop.call_later(timeout_dur, timeout_func)

            trans_func(**self._prune_kwargs(trans_func, prev_state=state, **kwargs))

        elif trans_type == StateTransition.EXIT:
            # Cancel timeout trigger (if any)
            if timeout_func and self.timeout_handler:
                self.log.debug("Canceling timeout trigger")
                self.timeout_handler.cancel()
                self.timeout_handler = None

            trans_func(**self._prune_kwargs(trans_func, next_state=state, **kwargs))

    def _get_input_handler(self, message, input_type: str):
        registry = getattr(self, input_type)
        assert isinstance(registry, dict), "Expected registry to be a dictionary!"

        func = registry[type(message)]

        assert hasattr(self, func.__name__), "STATE META LOGIC ERROR! Input handler for message type {} found to be" \
                                             " func {}, but no such attr name found on self {}"\
                                             .format(type(message), func, dir(self))

        return getattr(self, func.__name__)

    @classmethod
    def _has_envelope_arg(cls, func):
        # TODO more robust logic that searches through parameter type annotations one that is typed with Envelope class
        sig = inspect.signature(func)
        return 'envelope' in sig.parameters

    @classmethod
    def _prune_kwargs(cls, func, **kwargs):
        """
        Prunes kwargs s.t. only keys which are present as named args in func's signature are present.
        """
        params = inspect.signature(func).parameters
        return {k: kwargs[k] for k in kwargs if k in params}

    def _assert_has_input_handler(self, message: MessageBase, input_type: str):
        # Assert that input_type is actually a recognized input_type

        assert input_type in StateInput.ALL, "Input type {} not found in StateInputs {}"\
                                             .format(input_type, StateInput.ALL)
        # Assert that this state, or one of its superclasses, has an appropriate receiver implemented
        assert type(message) in getattr(self, input_type), \
            "No handler for message type {} found in handlers for input type {} which has handlers: {}"\
            .format(type(message), input_type, getattr(self, input_type))

    def _get_transition_handler(self, trans_type, state):
        assert trans_type in (StateTransition.ENTER, StateTransition.EXIT), "trans_type arg must be _ENTER or _EXIT"
        assert type(state) is str or issubclass(state, State),\
            "state arg must be a State class or the string of a State class name"

        # Cast state class to string if necessary
        if issubclass(state, State):
            state = state.__name__

        trans_registry = getattr(self, trans_type)

        # First see if a specific transition handler exists
        if state in trans_registry:
            func = trans_registry[state]
            assert hasattr(self, func.__name__), "STATE META LOGIC ERROR! Specific transition {} handler {} found for " \
                                                 "state {}, but no method of that named found on self {}"\
                                                 .format(trans_type, func, state, dir(self))
            return getattr(self, func.__name__)

        # Next, see if there is an ANY handler (a 'wildcard' handler configured to capture all states)
        any_handler = getattr(self, StateTransition.get_any_attr(trans_type))
        if any_handler:
            assert hasattr(self, any_handler.__name__), "STATE META LOGIC ERROR! General transition {} handler {} found" \
                                                        " for state {}, but no method of that named found on self {}" \
                                                        .format(trans_type, any_handler, state, dir(self))
            return getattr(self, any_handler.__name__)

        # At this point, no handler could be found. Warn the user and return None
        self.log.warning("\nNo {} transition handler found for state {}. Any_handler = {} ... Transition "
                         "Registry = {}".format(trans_type, state, any_handler, trans_registry))
        return None

    def __eq__(self, other):
        """
        An equality check on steroids. Used in State + StateMachine classes for type introspection. This
        method should return true if both self and other are the same CLASS of state. Other may be either another
        state instance, or a state class, or a string representing the name of a state class
        """
        # Case 1 -- 'other' is a State subclass
        if type(other) is StateMeta:
            return type(self) == other

        # Case 2 -- 'other' is a State instance
        elif isinstance(other, State):
            return type(self) == type(other)

        # Case 3 -- 'other' is a string
        elif type(other) is str:
            return self.__name__ == other

        # Otherwise, this is an invalid comparison ('other' belongs to unknown equivalence class)
        else:
            raise ValueError("Invalid comparison -- RHS (right hand side of equation) must be either a State subclass "
                             "instance or String or Class (not {})".format(other))

    def __repr__(self):
        return type(self).__name__


class EmptyState(State):
    def reset_attrs(self):
        pass

    @exit_to_any
    def exit_any(self, next_state):
        pass
