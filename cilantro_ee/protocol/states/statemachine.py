from cilantro_ee.protocol.states.state import State, EmptyState
from cilantro_ee.protocol.states.decorators import StateTransition
from cilantro_ee.utils import lazy_property
import inspect
import asyncio


class StateMachine:
    """
    TODO -- docstring
    """
    _STATES = []
    _INIT_STATE = None

    def __init__(self):
        """
        TODO -- docstring
        """
        # Sanity checks (mostly for catching dev bugs)
        assert len(self._STATES) > 0, \
            "_STATES is empty. Register states using class decorator @StateMachineSubclass.register_state"
        assert self._INIT_STATE is not None, \
            "_INIT_STATE is None. Add an init state using class decorator @StateMachineSubclass.register_init_state"
        assert self._INIT_STATE in self._STATES, "Init state {} not found in self._STATES {}".format(self._INIT_STATE,
                                                                                                     self._STATES)
        self.is_started = False

        # Instantiate state objects
        self.state = EmptyState(self)
        self.states = {s: s(self) for s in self._STATES}

    def start(self, run_in_loop=False):
        """
        Starts the StateMachine by transitioning into its initial state. If run_in_loop is True, then this method start
        an infinite event loop This is necessary for loop-using functionality like
        state timeouts.

        However, run_in_loop should always be false for Cilantro in production! This is because OldNodeBase, which is a
        StateMachine subclass, manages its own event loop, that is gaurenteed to run_forever once StateMachine.start()
        relinquishes control. run_in_loop=True should only be used in unit tests, or if the StateMachine class is intended
        to be used as a standalone library (outside of Cilantro).
        """
        assert not self.is_started, "StateMachine already started -- .start() must only be invoked once."

        self.is_started = True
        self.transition(self._INIT_STATE)

        if run_in_loop:
            self.loop = asyncio.get_event_loop()
            asyncio.set_event_loop(self.loop)

            # Sanity check to make sure if run_in_loop is True, then the default event loop is not already running
            assert not self.loop.is_running(), "Loop cannot already be running if run_in_loop is passed!"

            self._log("Running event loop forever")
            self.loop.run_forever()

    def transition(self, next_state, *args, **kwargs):
        """
        TODO thiccer docstrings
        :param next_state: The state to transition to. Must be a State class (not instance) or string.
        If it's a class, that class must exist in _STATES which is defined by the StateMachine subclass. If it's a
        string, a class of that name must exist in _STATES
        """
        # Validate next_state arg
        if type(next_state) is str:
            retrieved_state = self._state_cls_map.get(next_state)
            assert retrieved_state, "No state named {} found in self.states {} with _state_cls_map {}"\
                                    .format(next_state, self.states, self._state_cls_map)
            next_state = retrieved_state
        elif inspect.isclass(next_state) and issubclass(next_state, State):
            pass
        else:
            raise Exception("Invalid value of {} for 'next_state' in transition function args. 'next_state' must "
                            "be a State class, or the name of a State class as a string").format(next_state)

        assert next_state in self.states, "Transition next state {} not in states {}".format(next_state, self.states)

        ns = self.states[next_state]
        self._log("Transition from current state {} to next state {} ... with transition args {} and kwargs {}"
                  .format(self.state, next_state, args, kwargs))

        # Exit current state
        self.state.call_transition_handler(StateTransition.EXIT, type(ns), *args, **kwargs)

        # Set new state
        prev_state = self.state
        self.state = ns

        # Enter next (now current) state
        self.state.call_transition_handler(StateTransition.ENTER, type(prev_state), *args, **kwargs)

    @classmethod
    def register_state(cls, state_cls):
        """
        Decorator to register states in a StateMachine
        """
        assert inspect.isclass(state_cls), "@register_state decorator must applied on a class"
        assert issubclass(state_cls, State), "@register_state decorator must be applied to a State subclass"
        assert state_cls not in cls._STATES, "State class {} already in _STATES {}".format(state_cls, cls._STATES)

        cls._STATES.append(state_cls)

        return state_cls

    @classmethod
    def register_init_state(cls, state_cls):
        assert inspect.isclass(state_cls), "@register_state decorator must applied on a class"
        assert issubclass(state_cls, State), "@register_state decorator must be applied to a State subclass"
        assert cls._INIT_STATE is None, "_INIT_STATE is already set to {}. Only decorate one class with " \
                                        "@register_init_state (attempted to reset to {})".format(cls._INIT_STATE, state_cls)
        assert state_cls not in cls._STATES, "Initial state class {} found in _STATES {}. Do not use @register_state" \
                                             " AND @register_init_state; using only the latter will suffice"\
                                             .format(state_cls, cls._STATES)

        cls._STATES.append(state_cls)
        cls._INIT_STATE = state_cls

        return state_cls

    @lazy_property
    def _state_cls_map(self):
        assert self.is_started, "StateMachine should be started before _state_cls_map is read!"
        return {s.__name__: s for s in self.states}

    def _log(self, msg: str):
        """
        Attempts to log a message if this object has a property 'log' (which all BaseNodes should). If the object
        does not have this property, then this message is printed
        """
        if hasattr(self, 'log'):
            self.log.debugv(msg)
        else:
            print(msg)
