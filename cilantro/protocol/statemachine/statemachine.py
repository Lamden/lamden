from cilantro.protocol.statemachine.state import State, EmptyState
from typing import List


class StateMachine:
    """
    TODO -- docstring
    """
    def __init__(self, init_state: type(State), states: List[type(State)]):
        """
        TODO -- docstring
        :param init_state:
        :param states:
        """
        self.state = EmptyState(self)
        self.states = [s(self) for s in states]

        init_state_obj = next((s for s in self.states if s == init_state), None)
        assert init_state_obj is not None, "Attempted to init machine with state {} which was not found in " \
                               "list of states {}".format(init_state, self.states)

        self.transition(init_state_obj)

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
        ns = next((s for s in self.states if s == next_state), None)
        assert ns is not None, "Attempted to transition to unknown state {} which was not found in internal " \
                               "list of states {}".format(next_state, self.states)

        self.state.exit(ns)
        ns.enter(self.state)
        self.state = ns
        self.state.run()
