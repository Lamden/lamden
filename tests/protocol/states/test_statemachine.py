from unittest import TestCase
from .stumachine import *
from cilantro.protocol.states.state import StateInput

class StateMachineTest(TestCase):

    def test_register_decorators(self):
        """
        Tests the @StateMachine.register_state and .register_init_state decorators
        """
        self.assertTrue(StuMachine._INIT_STATE is SleepState)

        self.assertTrue(SleepState in StuMachine._STATES)
        self.assertTrue(LiftState in StuMachine._STATES)
        self.assertTrue(CodeState in StuMachine._STATES)

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

    def test_transition_calls_exit_any(self):
        """
        Tests that a transition calls an exit_any method
        """
        sm = StuMachine()

        sm.start()

        sm.transition(LiftState)

        self.assertTrue(type(sm.state) is LiftState)
        self.assertTrue(sm.sleep_did_exit_any)

    def test_transition_calls_exit_specific(self):
        """
        Tests that a specific exit transition is called when appropriate
        """
        sm = StuMachine()

        sm.start()

        sm.transition(LiftState)
        sm.transition(SleepState)

        self.assertTrue(sm.exit_lift_to_sleep_called)

    def test_transition_inside_input1(self):
        """
        Tests transition states inside a @input handler
        """
        sm = StuMachine()
        sleep_time = 9000
        sleep_msg = GoToSleepMessage(sleep_time)

        sm.start()

        sm.transition(LiftState)
        self.assertTrue(sm.state == LiftState)

        sm.state.call_input_handler(StateInput.INPUT, sleep_msg)

        self.assertTrue(sm.state == SleepState)
        self.assertEqual(sm.state.sleep_time, sleep_time)

    def test_transition_inside_input2(self):
        """
        Tests transition states inside a @input handler
        """
        sm = StuMachine()

        sm.start()

        lift = LiftState.SQUAT
        weight = 7000
        msg = LiftingTimeMessage(weight=weight, lift=lift)

        sm.state.call_input_handler(StateInput.INPUT, msg)

        self.assertTrue(sm.state == LiftState)
        self.assertEqual(sm.state.current_lift, lift)
        self.assertEqual(sm.state.current_weight, weight)

    def test_transition_inside_enter(self):
        """
        Tests transitioning inside the enter method of a state
        """
        sm = StuMachine()

        sm.start()

        self.assertTrue(sm.state == SleepState)

        sm.transition(CodeState)  # the transition handler logic for this should put stu back to sleep

        self.assertTrue(sm.state == SleepState)


