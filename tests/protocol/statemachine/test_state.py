from unittest import TestCase
from unittest.mock import MagicMock
from cilantro.protocol.statemachine import *
"""
So we basically want to test...

1) input/input_request/timeout decorator 
2) input/input_request/timeout decorator inheritance + polymorphism

3) enter/exit called appropriately on transition
4) state_enter/state_exit decorators 
"""
class Message:
    def __init__(self, msg):
        self.msg = msg

    def __repr__(self):
        return self.msg


class ForceStopMessage(Message): pass
class RebootMessage(Message): pass
class StatusRequest(Message): pass
class MysteriousMessage(Message): pass


class TrafficLightBaseState(State):
    @input(ForceStopMessage)
    def handle_stop_msg_on_base(self, msg: ForceStopMessage):
        pass

    @input(RebootMessage)
    def handle_reboot_on_base(self, msg: RebootMessage):
        pass

    @enter_from_any
    def enter_general(self, prev_state):
        pass


class TrafficLightBrokenState(State): pass
class TrafficLightFixingState(State): pass


class TrafficLightRedState(TrafficLightBaseState):

    @input(RebootMessage)
    def handle_reboot_on_red(self, msg: RebootMessage):
        pass

    @input(ForceStopMessage)
    def handle_stop_msg_on_red(self, msg: ForceStopMessage, envelope):
        self.message = msg
        self.envelope = envelope

    @enter_from_any
    def enter_general(self, prev_state):
        pass

    @exit_from_any
    def exit_general(self, next_state):
        pass


class TrafficLightYellowState(TrafficLightBaseState):
    @input(ForceStopMessage)
    def handle_stop_msg_on_yellow(self, msg: ForceStopMessage):
        pass

    @enter_from(TrafficLightRedState)
    def enter_from_red(self, prev_state):
        pass

    @enter_from(TrafficLightBrokenState, TrafficLightFixingState)
    def enter_from_broken_or_fixing(self, prev_state):
        pass


class TrafficLightGreenState(TrafficLightBaseState):
    @input_request(StatusRequest)
    def handle_status_req_on_green(self, request: StatusRequest, envelope):
        self.request = request


STATES = [TrafficLightGreenState, TrafficLightRedState, TrafficLightYellowState]


class StateTest(TestCase):

    def assert_funcs_equal(self, func1, func2):
        """
        Hackish helper method to assert two functions have the same name
        Necessary b/c _get_input_handler returns a function (ie. SomeStateClass.handle_this), versus a bounded method
        (i.e. some_state_instance.handle_this)
        """
        self.assertEqual(func1.__qualname__, func2.__qualname__)

    def test_enter_any_decorator(self):
        mock_sm = MagicMock()

        state = TrafficLightRedState(mock_sm)

        self.assertTrue(hasattr(state.enter_general, TransitionDecor.ENTER))
        self.assertEqual(getattr(state.enter_general, TransitionDecor.ENTER), TransitionDecor.ACCEPT_ALL)

    def test_exit_any_decorator(self):
        mock_sm = MagicMock()

        state = TrafficLightRedState(mock_sm)

        self.assertTrue(hasattr(state.exit_general, TransitionDecor.EXIT))
        self.assertEqual(getattr(state.exit_general, TransitionDecor.EXIT), TransitionDecor.ACCEPT_ALL)

    def test_enter_from_one_decorator(self):
        mock_sm = MagicMock()

        state = TrafficLightYellowState(mock_sm)

        self.assertTrue(hasattr(state.enter_from_red, TransitionDecor.ENTER))

        entries_arr = getattr(state.enter_from_red, TransitionDecor.ENTER)

        self.assertTrue(type(entries_arr) is list)
        self.assertTrue(len(entries_arr) == 1)
        self.assertTrue(entries_arr[0] is TrafficLightRedState)

    def test_enter_from_two_decorator(self):
        mock_sm = MagicMock()

        state = TrafficLightYellowState(mock_sm)

        self.assertTrue(hasattr(state.enter_from_broken_or_fixing, TransitionDecor.ENTER))

        entries_arr = getattr(state.enter_from_broken_or_fixing, TransitionDecor.ENTER)

        self.assertTrue(type(entries_arr) is list)
        self.assertTrue(len(entries_arr) == 2)
        self.assertTrue(TrafficLightFixingState in entries_arr)
        self.assertTrue(TrafficLightBrokenState in entries_arr)

    def test_get_transition_handler_any(self):
        """
        """
        mock_sm = MagicMock()
        stop_msg = ForceStopMessage("stop it dude srsly")

        state = TrafficLightBaseState(mock_sm)

        expected_handler = TrafficLightBaseState.enter_general
        actual_handler = state._get_transition_handler(TransitionDecor.ENTER, EmptyState)

        self.assert_funcs_equal(expected_handler, actual_handler)

    def test_get_input_handler_with_input(self):
        """
        Tests _get_input_handler with input type StateInput.INPUT
        """
        mock_sm = MagicMock()
        stop_msg = ForceStopMessage("stop it guy")

        state = TrafficLightBaseState(mock_sm)

        expected_handler = TrafficLightBaseState.handle_stop_msg_on_base
        actual_handler = state._get_input_handler(stop_msg, StateInput.INPUT)

        self.assert_funcs_equal(expected_handler, actual_handler)

    def test_get_input_handler_with_request(self):
        mock_sm = MagicMock()
        msg = StatusRequest("how u doin guy")

        state = TrafficLightGreenState(mock_sm)

        expected_handler = TrafficLightGreenState.handle_status_req_on_green
        actual_handler = state._get_input_handler(msg, StateInput.REQUEST)

        self.assert_funcs_equal(expected_handler, actual_handler)

    def test_get_input_handler_inheritance(self):
        mock_sm = MagicMock()
        stop_msg = ForceStopMessage("stop it guy")

        state = TrafficLightYellowState(mock_sm)

        expected_handler = TrafficLightYellowState.handle_stop_msg_on_yellow
        actual_handler = state._get_input_handler(stop_msg, StateInput.INPUT)

        self.assert_funcs_equal(expected_handler, actual_handler)

    def test_get_input_handler_inheritance_override(self):
        """
        """
        mock_sm = MagicMock()
        reboot_msg = RebootMessage("reboot it guy")

        state = TrafficLightYellowState(mock_sm)

        expected_handler = TrafficLightBaseState.handle_reboot_on_base
        actual_handler = state._get_input_handler(reboot_msg, StateInput.INPUT)

        self.assert_funcs_equal(expected_handler, actual_handler)

    def test_assert_has_input_handler(self):
        mock_sm = MagicMock()
        strange_msg = MysteriousMessage("lol u dont have a receiver for me do u")

        state = TrafficLightBaseState(mock_sm)

        self.assertRaises(Exception, state._assert_has_input_handler, strange_msg, StateInput.INPUT)

    def test_has_envelope_arg(self):
        mock_sm = MagicMock()
        msg = StatusRequest("how u doin guy")

        state = TrafficLightGreenState(mock_sm)

        expected_handler = TrafficLightGreenState.handle_status_req_on_green
        func = state._get_input_handler(msg, StateInput.REQUEST)

        self.assert_funcs_equal(expected_handler, func)
        self.assertTrue(state._has_envelope_arg(func))

    def test_call_input_handler(self):
        mock_sm = MagicMock()
        msg = StatusRequest("how u doin guy")

        state = TrafficLightGreenState(mock_sm)

        expected_handler = TrafficLightGreenState.handle_status_req_on_green
        func = state._get_input_handler(msg, StateInput.REQUEST)

        self.assert_funcs_equal(expected_handler, func)

        state.call_input_handler(msg, StateInput.REQUEST)

        self.assertEqual(state.request, msg)

    def test_call_input_handler_with_envelope(self):
        mock_sm = MagicMock()
        mock_env = MagicMock()
        msg = ForceStopMessage("stop it guy!")

        state = TrafficLightRedState(mock_sm)

        state.call_input_handler(msg, StateInput.INPUT, envelope=mock_env)

        self.assertEqual(state.message, msg)
        self.assertEqual(state.envelope, mock_env)
