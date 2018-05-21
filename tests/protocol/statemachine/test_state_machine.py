from cilantro.protocol.statemachine import *
from unittest import TestCase


"""
This stuff is a little tricky to test. In interest of optimizing utility per unit of time, we just create a toy example 
StateMachine class, with toy states, and use this in our test cases. 
The proper way to do this would prolly be to mock all this stuff, but that would be hella tedious.  
"""

DEFAULT_LIFT = None
DEFAULT_WEIGHT = 0


class SleepState(State):
    def reset_attrs(self):
        pass

    def enter(self, prev_state, *args, **kwargs):
        pass

    def exit(self, next_state, *args, **kwargs):
        pass

    def run(self):
        pass

    # @enter_state
    def enter_general(self, prev_state):
        self.log.debug("general entry from prev state {}".format(prev_state))

class CodeState(State):
    def reset_attrs(self):
        self.lang = None
        self.activity = None

    def enter_any(self, prev_state, *args, **kwargs):
        pass

    def exit_any(self, next_state, *args, **kwargs):
        pass

    def run(self):
        pass

    @enter_from_any
    def enter_general(self, prev_state):
        self.log.debug("general entry from prev state {}".format(prev_state))

    @enter_from(SleepState)
    def enter_from_sleep(self, prev_state):
        self.log.debug("SLEEP STATE SPECIFIC entered from previous state {}".format(prev_state))

class LiftState(State):
    BENCH, SQUAT, DEADLIFT = 'BENCH', 'SQUAT', 'DEAD LIFT'

    def reset_attrs(self):
        self.current_lift = DEFAULT_LIFT
        self.current_weight = DEFAULT_WEIGHT

    @enter_from_any
    def enter_any(self, prev_state, lift=False, weight=False):
        self.log.debug("Entering state from prev {} with lift {} and weight {}".format(prev_state, lift, weight))

        if weight:
            self.current_weight = weight
        if lift:
            self.current_lift = lift

    @enter_from(CodeState)
    def enter_from_code(self, prev_state, lift=False, weight=False):
        self.log.debug("CODESTATE SPECIFIC entering from prev state {}".format(prev_state))
        self.reset_attrs()

    def run(self):
        pass

    def lift(self):
        self.log.debug("Doing lift: {} ... with weight: {}".format(self.current_lift, self.current_weight))


class StuMachine(StateMachine):
    _INIT_STATE = SleepState
    _STATES = [SleepState, CodeState, LiftState]


class StateMachineTest(TestCase):

    # FOR DEBUGGING TODO remove this later
    def test_experiment(self):
        sm = StuMachine()

        sm.start()

    def test_start(self):
        """
        Tests that a state machine starts, and enter the desired boot state
        """
        sm = StuMachine()

        sm.start()

        self.assertTrue(type(sm.state) is SleepState)

    def test_transition(self):
        """
        Tests that a state machine transitions into the correct state when instructed to do so
        """
        sm = StuMachine()

        sm.start()

        sm.transition(LiftState)

        self.assertTrue(type(sm.state) is LiftState)

    def test_transition_args(self):
        """
        Tests transitioning into a state with args produced to intended effect
        """
        sm = StuMachine()

        sm.start()

        lift = LiftState.SQUAT
        weight = 9000

        sm.transition(LiftState, lift=lift, weight=weight)

        self.assertTrue(type(sm.state) is LiftState)
        self.assertEqual(sm.state.current_lift, lift)
        self.assertEqual(sm.state.current_weight, weight)

    def test_transition_resets_attrs(self):
        """
        Tests that attributes are reset when a state is transitioned into
        """
        sm = StuMachine()

        sm.start()

        lift = LiftState.SQUAT
        weight = 9000

        sm.transition(LiftState, lift=lift, weight=weight)

        self.assertTrue(type(sm.state) is LiftState)
        self.assertEqual(sm.state.current_lift, lift)
        self.assertEqual(sm.state.current_weight, weight)

        sm.transition(CodeState)

        self.assertTrue(type(sm.state) is CodeState)

        sm.transition(LiftState)

        self.assertTrue(type(sm.state) is LiftState)
        self.assertEqual(sm.state.current_lift, DEFAULT_LIFT)
        self.assertEqual(sm.state.current_weight, DEFAULT_WEIGHT)
