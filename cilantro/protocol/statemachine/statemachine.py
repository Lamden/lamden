from cilantro.protocol.statemachine.state import State, EmptyState
from typing import List


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
        states = self._STATES
        init_state = self._INIT_STATE

        assert states is not None, "_STATES is None (did you set it in the subclass?)"
        assert init_state is not None, "_INIT_STATE is None (did you set it in the subclass?)"

        self.state = EmptyState(self)
        print(states)
        self.states = {s: s(self) for s in states}
        assert init_state in self.states, "Init state {} not in states {}".format(init_state, self.states)

        self.transition(init_state)

    """
    NOTE: with this approach all internal attributes of each state persist between transitions.
    Is this what we want? or should each state be dealloc'd on exit(...) and alloc a new state before enter(...)?
    """
    def transition(self, next_state: type(State)):
        """
        TODO -- docstring
        :param next_state:
        :return:
        """
        # print("\n---- STARTING TRANSITION -----")
        # print("StateMachine transition to state: ", next_state)
        assert next_state in self.states, "Next state {} not in states {}".format(next_state, self.states)
        ns = self.states[next_state]

        self.state.exit(ns)
        ns.enter()
        self.state = ns
        self.state.run()

        # print("\n---- ENDING TRANSITION -----")
