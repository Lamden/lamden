EMPTY_STATE = "EMPTY_STATE"


class State:
    name = EMPTY_STATE

    def __init__(self, state_machine=None):
        assert state_machine is not None, "Cannot create state without a pointer to its encompassing state machine"
        self.sm = state_machine

    def handle_message(self, msg):
        raise NotImplementedError

    def enter(self, prev_state):
        raise NotImplementedError

    def exit(self, next_state):
        raise NotImplementedError

    def run(self):
        raise NotImplementedError

    def __eq__(self, other):
        return self.name == other.name

    def __ne__(self, other):
        return self.name != other.name


class EmptyState(State):
    def enter(self, prev_state):
        print("{} transitioning FROM state: {}".format(self.name, prev_state.name))

    def exit(self, next_state):
        print("{} transitioning TO state: {}".format(self.name, next_state.name))
