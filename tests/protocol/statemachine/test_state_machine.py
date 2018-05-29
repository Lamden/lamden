from cilantro.protocol.statemachine import *
from unittest import TestCase


"""
This stuff is a little tricky to test. In interest of optimizing utility per unit of time, we just create a toy example 
StateMachine class, with toy states, and use this in our test cases. So these are more like state machine integration
tests than unit tests.  

The proper way to do this would prolly be to mock all this stuff, but that would be hella tedious and quite fragile.  
"""

DEFAULT_LIFT = None
DEFAULT_WEIGHT = 0
DEFAULT_SLEEP_TIME = 8


class LiftingTimeMessage:
    def __init__(self, weight, lift):
        self.weight = weight
        self.lift = lift

class GoToSleepMessage:
    def __init__(self, sleep_time=DEFAULT_SLEEP_TIME):
        self.sleep_time = sleep_time


class SleepState(State):
    def reset_attrs(self):
        self.did_enter = False
        self.sleep_time = DEFAULT_SLEEP_TIME

    @input(LiftingTimeMessage)
    def handle_lifting_message(self, msg: LiftingTimeMessage):
        self.log.debug("Got lifting msg ... transitioning to lift state")
        # TODO implment once we can represent states as strings...
        # self.parent.transition()

    @enter_from_any
    def enter_general(self, prev_state, sleep_time = DEFAULT_SLEEP_TIME):
        self.log.debug("general entry from prev state {}".format(prev_state))
        self.sleep_time = sleep_time
        self.did_enter = True


class CodeState(State):
    def reset_attrs(self):
        self.lang = None
        self.activity = None

    # def enter_any(self, prev_state, *args, **kwargs):
    #     pass
    #
    # def exit_any(self, next_state, *args, **kwargs):
    #     pass

    # If the StuMachine tries to code first thing in the morn before lifting he goes back to sleep
    # @enter_from(SleepState)
    @enter_from("SleepState")
    def enter_from_sleep(self, prev_state):
        assert prev_state is SleepState, "wtf prev_state is not sleep state .... ?"

        self.log.debug("Entering CodeState from sleep state. Nah. Going back to bed.")
        self.parent.transition(SleepState)

    @enter_from_any
    def enter_general(self, prev_state):
        self.log.debug("general entry from prev state {}".format(prev_state))

    # @enter_from(SleepState)
    # def enter_from_sleep(self, prev_state):
    #     self.log.debug("SLEEP STATE SPECIFIC entered from previous state {}".format(prev_state))

class LiftState(State):
    BENCH, SQUAT, DEADLIFT = 'BENCH', 'SQUAT', 'DEAD LIFT'

    def reset_attrs(self):
        self.current_lift = DEFAULT_LIFT
        self.current_weight = DEFAULT_WEIGHT

    # TODO exit_any test

    @input(GoToSleepMessage)
    def handle_sleep_msg(self, msg: GoToSleepMessage):
        self.log.debug("Got sleep message to sleep for {} hours".format(msg))
        self.parent.transition(SleepState, sleep_time=msg.sleep_time)

    @enter_from_any
    def enter_any(self, prev_state, lift=False, weight=False):
        self.log.debug("Entering state from prev {} with lift {} and weight {}".format(prev_state, lift, weight))

        if weight:
            self.current_weight = weight
        if lift:
            self.current_lift = lift

    @enter_from("CodeState")
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

    def test_start(self):
        """
        Tests that a state machine starts, and enters the desired boot state
        """
        sm = StuMachine()

        sm.start()

        self.assertTrue(type(sm.state) is SleepState)
        self.assertTrue(sm.state.did_enter)

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

    def test_transition_inside_input(self):
        """
        Tests transition states inside a @input handler
        """
        sm = StuMachine()
        sleep_time = 9000
        sleep_msg = GoToSleepMessage(sleep_time)

        sm.start()

        sm.transition(LiftState)
        self.assertTrue(sm.state == LiftState)

        sm.state.call_input_handler(sleep_msg, StateInput.INPUT)

        self.assertTrue(sm.state == SleepState)
        self.assertEqual(sm.state.sleep_time, sleep_time)

    def test_transition_inside_enter(self):
        """
        Tests transitioning inside the enter method of a state
        """
        sm = StuMachine()

        sm.start()

        self.assertTrue(sm.state == SleepState)

        sm.transition(CodeState)  # the transition handler logic for this should put stu back to sleep

        self.assertTrue(sm.state == SleepState)



