import time

EMPTY_STATE = "EMPTY_STATE"
BOOT_STATE = "BOOT_STATE"
INTERPRETING_STATE = "INTERPRETING_STATE"
PERFORMING_CONSENSUS_STATE = "PERFORMING_CONSENSUS_STATE"


class NodeState:
    name = EMPTY_STATE

    def __init__(self, state_machine=None):
        self.sm = state_machine

    def handle_message(self, packet):
        raise NotImplementedError

    # should this just be called enter?
    def enter(self, prev_state):
        raise NotImplementedError

    # and can this just be called exit
    # WE REALLY ONLY NEED TRANSITION_FROM, RIGHT?
    #  (empty state --> boot must cannot have its transition defined in transition to)
    def exit(self, next_state):
        raise NotImplementedError

    def __eq__(self, other):
        return self.name == other.name

    def __ne__(self, other):
        return self.name != other.name

class EmptyState(NodeState):
    def enter(self, prev_state):
        print("EmptyState transitioning FROM state: {}".format(prev_state.name))

    def exit(self, next_state):
        print("EmptyState transitioning TO state: {}".format(next_state.name))

class BootState(NodeState):
    name = BOOT_STATE

    def enter(self, prev_state):
        print("BootState transitioning FROM state: {}".format(prev_state.name))
        print('blah blah blah im booting')
        time.sleep(0.75)
        self.sm.x['has_booted'] = True
        self.sm.transition(InterpretingState)

    def exit(self, next_state):
        print("BootState transitioning TO state: {}".format(next_state.name))


class InterpretingState(NodeState):
    name = INTERPRETING_STATE

    def enter(self, prev_state):
        print("InterpretingState transitioning FROM state: {}".format(prev_state.name))

    def exit(self, next_state):
        print("InterpretingState transitioning TO state: {}".format(next_state.name))

    def handle_message(self, packet):
        print("Interpreting state got packet: {}".format(packet))


class PerformingConsensusState(NodeState):
    name = PERFORMING_CONSENSUS_STATE

    def enter(self, prev_state):
        print("PerformingConsensusState transitioning FROM state: {}".format(prev_state.name))

    def exit(self, next_state):
        print("PerformingConsensusState transitioning TO state: {}".format(next_state.name))

    def handle_message(self, packet):
        print("Consensus state got packet: {}".format(packet))


class StateMachine:
    def __init__(self, init_state: type(NodeState), states: list):
        self.state = EmptyState(self)
        self.states = [s(self) for s in states]
        init_state_obj = next((s for s in self.states if s == init_state), None)


        # Global shared values
        self.x = {}
        self.y = "FLUFFY CATS"
        self.z = 'THICC DOGGOS'

        # Start initial state
        self.transition(init_state_obj)


    # How to call this on individual states?
    def some_machine_func(self, msg):
        print("Some machine func called with msg: {}".format(msg))

    def some_callback_func(self, msg):
        print("Some callback func called with msg: {}".format(msg))

    # NOTE: with this approach all internal attributes of each state persist between transitions
    # is this what we want? or should we alloc a new state class each time we transition and effectively reset the state
    def transition(self, next_state: type(NodeState)):
        ns = next((s for s in self.states if s == next_state), None)
        assert ns is not None, "Attempted to transition to unknown state {} which was not found in internal " \
                               "list of states {}".format(next_state, self.states)

        self.state.exit(ns)
        ns.enter(self.state)
        self.state = ns


STATES = [BootState, InterpretingState, PerformingConsensusState]
INIT_STATE = BootState
sm = StateMachine(INIT_STATE, STATES)




