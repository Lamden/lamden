from cilantro.protocol.statemachine.state import State, EmptyState
from cilantro.protocol.statemachine.decorators import TransitionDecor


class StateMachine:
    """
    TODO -- docstring
    """
    _STATES = None
    _INIT_STATE = None

    def __init__(self):
        """
        TODO -- docstring
        """
        self.is_started = False

        assert self._STATES is not None, "_STATES is None (did you set it in the StateMachine subclass?)"
        assert self._INIT_STATE is not None, "_INIT_STATE is None (did you set it in the StateMachine subclass?)"

        self.state = EmptyState(self)
        self.states = None

    def start(self):
        """
        Starts the StateMachine by instantiating all state classes, and then transitioning the machine into its
        initial state
        """
        assert not self.is_started, "StateMachine already started -- .start() must only be invoked once."

        states = self._STATES
        init_state = self._INIT_STATE

        self.states = {s: s(self) for s in states}
        assert init_state in self.states, "Init state {} not in states {}".format(init_state, self.states)

        self.is_started = True
        self.transition(init_state)

    def transition(self, next_state: type(State), *args, **kwargs):
        """
        TODO thiccer docstrings
        :param next_state: The state to transition to. Must be a State class (not instance), and that class must be
        exist _STATES which is defined by the StateMachine subclass
        """
        assert issubclass(next_state, State), "next_state {} is not a subclass of State".format(next_state)
        assert next_state in self.states, "Transition next state {} not in states {}".format(next_state, self.states)

        ns = self.states[next_state]
        self._log("Transition from current state {} to next state {} ... with transition args {} and kwargs {}"
                  .format(self.state, next_state, args, kwargs))

        # Exit next state
        self.state.call_transition_handler(TransitionDecor.EXIT, type(ns), *args, **kwargs)

        # Set new state
        prev_state = self.state
        self.state = ns

        # Enter next state
        self.state.call_transition_handler(TransitionDecor.ENTER, type(prev_state), *args, **kwargs)

    def _log(self, msg: str):
        """
        Attempts to log a message if this object has a property 'log' (which all BaseNodes should). If the object
        does not have this property, then this message is printed
        """
        if hasattr(self, 'log'):
            self.log.debug(msg)
        else:
            print(msg)


