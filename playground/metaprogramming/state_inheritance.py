from cilantro.protocol.statemachine.state import State
from cilantro.protocol.statemachine.statemachine import StateMachine


class Node(StateMachine):

    def __init__(self, init_state=None, states=None):
        STATES = [StartState, RunState]
        INIT_STATE = StartState

        self.a = 'hello'
        self.b = [1, 2, 3]
        self.c = {'node': 'is_here'}


        super().__init__(INIT_STATE, STATES)



class StartState(State):
    def enter(self, prev_state):
        self.log.info("entering state from prev_state {}".format(prev_state))
    def exit(self, next_state):
        self.log.info("exiting state to next {}".format(next_state))
        self.sm.a = 'start state goodbye'
    def run(self):
        self.log.info("running")
        self.log.info("self.sm.a: {}".format(self.sm.a))
        self.sm.transition(RunState)

class RunState(State):
    def enter(self, prev_state):
        self.log.info("entering state from prev_state {}".format(prev_state))
    def exit(self, next_state):
        self.log.info("exiting state to next {}".format(next_state))
        self.sm.a = 'start state goodbye'
    def run(self):
        self.log.info("running")
        self.log.info("self.sm.a: {}".format(self.sm.a))


if __name__ == "__main__":

    node = Node()