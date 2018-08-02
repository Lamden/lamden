from unittest import TestCase
from unittest.mock import MagicMock, patch
from .trafficlight import *
from cilantro.protocol.states.decorators import StateTimeout, StateTransition, StateInput
from cilantro.protocol.states.state import EmptyState

class StateTest(TestCase):

    def test_eq_instance(self):
        mock_sm = MagicMock()

        state1 = TrafficLightYellowState(mock_sm)
        state2 = TrafficLightYellowState(mock_sm)

        self.assertTrue(state1 == state2)

    def test_eq_class(self):
        mock_sm = MagicMock()

        state1 = TrafficLightYellowState(mock_sm)

        self.assertTrue(state1 == TrafficLightYellowState)

    def test_eq_instance_false(self):
        mock_sm = MagicMock()

        state1 = TrafficLightYellowState(mock_sm)
        state2 = TrafficLightRedState(mock_sm)

        self.assertFalse(state1 == state2)

    def test_eq_class_false(self):
        mock_sm = MagicMock()

        state1 = TrafficLightYellowState(mock_sm)

        self.assertFalse(state1 == TrafficLightRedState)

    def test_eq_raises(self):
        def comp_states(state1, state2):
            return state1 == state2

        mock_sm = MagicMock()

        state = TrafficLightYellowState(mock_sm)
        not_a_state = {'this is fersure': 'not a state instance or class lol'}

        self.assertRaises(ValueError, comp_states, state, not_a_state)

    def test_prune_kwargs(self):
        def some_func(arg1='hello', arg2='goodbye'):
            pass

        kwargs = {'arg2': 9000, 'key that isnt an arg in some_func': b'hi'}

        expected_kwargs = {'arg2': 9000}
        pruned_kwargs = State._prune_kwargs(some_func, **kwargs)

        self.assertEqual(expected_kwargs, pruned_kwargs)

    def test_config_timeout_func(self):
        timeout_func = getattr(TrafficLightYellowState, StateTimeout.TIMEOUT_FLAG)
        timeout_dur = getattr(TrafficLightYellowState, StateTimeout.TIMEOUT_DUR)

        self.assertEqual(timeout_func, TrafficLightYellowState.timeout)
        self.assertEqual(YELLOW_TIMEOUT_DUR, timeout_dur)

    def test_config_timeout_func_none(self):
        timeout_func = getattr(TrafficLightRedState, StateTimeout.TIMEOUT_FLAG)
        self.assertEqual(timeout_func, None)

    def test_enter_any_decorator(self):
        mock_sm = MagicMock()

        state = TrafficLightRedState(mock_sm)

        self.assertTrue(hasattr(state.enter_general, StateTransition.ENTER))
        self.assertEqual(getattr(state.enter_general, StateTransition.ENTER), StateTransition.ACCEPT_ALL)

    def test_exit_any_decorator(self):
        mock_sm = MagicMock()

        state = TrafficLightRedState(mock_sm)

        self.assertTrue(hasattr(state.exit_general, StateTransition.EXIT))
        self.assertEqual(getattr(state.exit_general, StateTransition.EXIT), StateTransition.ACCEPT_ALL)

    def test_config_trans_exit_doesnt_exit(self):
        mock_sm = MagicMock()

        state = TrafficLightYellowState(mock_sm)

        self.assertTrue(hasattr(state, StateTransition.ENTER))
        self.assertTrue(hasattr(state, StateTransition.EXIT))

        self.assertTrue(type(getattr(state, StateTransition.EXIT)) is dict)
        self.assertTrue(getattr(state, StateTransition.EXIT) == {})

    def test_enter_from_one_decorator(self):
        mock_sm = MagicMock()

        state = TrafficLightYellowState(mock_sm)

        self.assertTrue(hasattr(state.enter_from_red, StateTransition.ENTER))

        entries_arr = getattr(state.enter_from_red, StateTransition.ENTER)

        self.assertTrue(type(entries_arr) is list)
        self.assertTrue(len(entries_arr) == 1)
        self.assertTrue(TrafficLightRedState.__name__ == entries_arr[0])

    def test_enter_from_two_decorator(self):
        mock_sm = MagicMock()

        state = TrafficLightYellowState(mock_sm)

        self.assertTrue(hasattr(state.enter_from_broken_or_fixing, StateTransition.ENTER))

        entries_arr = getattr(state.enter_from_broken_or_fixing, StateTransition.ENTER)

        self.assertTrue(type(entries_arr) is list)
        self.assertTrue(len(entries_arr) == 2)
        self.assertTrue(TrafficLightFixingState.__name__ in entries_arr or TrafficLightFixingState in entries_arr)
        self.assertTrue(TrafficLightBrokenState.__name__ in entries_arr or TrafficLightBrokenState in entries_arr)

    def test_get_transition_handler_any(self):
        mock_sm = MagicMock()

        state = TrafficLightBaseState(mock_sm)

        expected_handler = state.enter_general
        actual_handler = state._get_transition_handler(StateTransition.ENTER, EmptyState)

        self.assertEqual(expected_handler, actual_handler)

    def test_get_transition_handler_exit_any(self):
        mock_sm = MagicMock()

        state = TrafficLightRedState(mock_sm)

        expected_handler = state.exit_general
        actual_handler = state._get_transition_handler(StateTransition.EXIT, TrafficLightYellowState)

        self.assertEqual(expected_handler, actual_handler)

    def get_transition_handler_specific(self):
        mock_sm = MagicMock()

        state = TrafficLightYellowState(mock_sm)

        expected_handler = state.enter_from_red
        actual_handler = state._get_transition_handler(StateTransition.ENTER, TrafficLightRedState)

        self.assertEqual(expected_handler, actual_handler)

    def test_get_trans_enter_any_doesnt_exist(self):
        mock_sm = MagicMock()

        state = TrafficLightGreenState(mock_sm)

        expected_handler = None
        actual_handler = state._get_transition_handler(StateTransition.ENTER, EmptyState)

        self.assertEqual(expected_handler, actual_handler)

    def test_get_input_handler_with_input(self):
        """
        Tests _get_input_handler with input type StateInput.INPUT
        """
        mock_sm = MagicMock()
        stop_msg = ForceStopMessage("stop it guy")

        state = TrafficLightBaseState(mock_sm)

        expected_handler = state.handle_stop_msg_on_base
        actual_handler = state._get_input_handler(stop_msg, StateInput.INPUT)

        self.assertEqual(expected_handler, actual_handler)

    def test_get_input_handler_with_request(self):
        mock_sm = MagicMock()
        msg = StatusRequest("how u doin guy")

        state = TrafficLightGreenState(mock_sm)

        expected_handler = state.handle_status_req_on_green
        actual_handler = state._get_input_handler(msg, StateInput.REQUEST)

        self.assertEqual(expected_handler, actual_handler)

    def test_get_input_handler_inheritance(self):
        mock_sm = MagicMock()
        stop_msg = ForceStopMessage("stop it guy")

        state = TrafficLightYellowState(mock_sm)

        expected_handler = state.handle_stop_msg_on_yellow
        actual_handler = state._get_input_handler(stop_msg, StateInput.INPUT)

        self.assertEqual(expected_handler, actual_handler)

    def test_get_input_handler_inheritance_override(self):
        """
        """
        mock_sm = MagicMock()
        reboot_msg = RebootMessage("reboot it guy")

        state = TrafficLightYellowState(mock_sm)

        expected_handler = state.handle_reboot_on_base
        actual_handler = state._get_input_handler(reboot_msg, StateInput.INPUT)

        self.assertEqual(expected_handler, actual_handler)

    def test_assert_has_input_handler(self):
        mock_sm = MagicMock()
        strange_msg = MysteriousMessage("lol u dont have a receiver for me do u")

        state = TrafficLightBaseState(mock_sm)

        self.assertRaises(Exception, state._assert_has_input_handler, strange_msg, StateInput.INPUT)

    def test_has_envelope_arg(self):
        mock_sm = MagicMock()
        msg = StatusRequest("how u doin guy")

        state = TrafficLightGreenState(mock_sm)

        expected_handler = state.handle_status_req_on_green
        func = state._get_input_handler(msg, StateInput.REQUEST)

        self.assertEqual(expected_handler, func)
        self.assertTrue(state._has_envelope_arg(func))

    def test_call_input_handler(self):
        mock_sm = MagicMock()
        mock_env = MagicMock()
        msg = StatusRequest("how u doin guy")

        state = TrafficLightGreenState(mock_sm)

        expected_handler = state.handle_status_req_on_green
        func = state._get_input_handler(msg, StateInput.REQUEST)

        self.assertEqual(expected_handler, func)

        state.call_input_handler(msg, StateInput.REQUEST, envelope=mock_env)

        self.assertEqual(state.request, msg)

    def test_call_input_handler_with_envelope(self):
        mock_sm = MagicMock()
        mock_env = MagicMock()
        msg = ForceStopMessage("stop it guy!")

        state = TrafficLightRedState(mock_sm)

        state.call_input_handler(msg, StateInput.INPUT, envelope=mock_env)

        self.assertEqual(state.message, msg)
        self.assertEqual(state.envelope, mock_env)

    def test_call_input_handler_enter_doesnt_exist(self):
        """
        TODO -- test that call_input_handler raises an exception if the handler does not exist
        """
        self.assertTrue(2 + 2 == 4)

    def test_get_transition_handler_enter_general(self):
        mock_sm = MagicMock()

        state = TrafficLightRedState(mock_sm)

        expected_handler = state.enter_general
        actual_handler = state._get_transition_handler(StateTransition.ENTER, EmptyState)

        self.assertEqual(expected_handler, actual_handler)

    def test_get_transition_handler_exit_general(self):
        mock_sm = MagicMock()

        state = TrafficLightRedState(mock_sm)

        expected_handler = state.exit_general
        actual_handler = state._get_transition_handler(StateTransition.EXIT, EmptyState)

        self.assertEqual(expected_handler, actual_handler)

    def test_get_transition_handler_exit_specific(self):
        mock_sm = MagicMock()

        state = TrafficLightRedState(mock_sm)

        expected_handler = state.exit_from_maintenance
        actual_handler1 = state._get_transition_handler(StateTransition.EXIT, TrafficLightBrokenState)
        actual_handler2 = state._get_transition_handler(StateTransition.EXIT, TrafficLightFixingState)

        self.assertEqual(expected_handler, actual_handler1)
        self.assertEqual(expected_handler, actual_handler2)

    def test_get_transition_handler_none(self):
        mock_sm = MagicMock()

        state = TrafficLightGreenState(mock_sm)

        expected_handler = None
        actual_handler1 = state._get_transition_handler(StateTransition.EXIT, TrafficLightBrokenState)
        actual_handler2 = state._get_transition_handler(StateTransition.ENTER, TrafficLightFixingState)

        self.assertEqual(expected_handler, actual_handler1)
        self.assertEqual(expected_handler, actual_handler2)

    def test_get_transition_handler_enter_specific(self):
        mock_sm = MagicMock()

        state = TrafficLightYellowState(mock_sm)

        expected_handler = state.enter_from_broken_or_fixing
        actual_handler1 = state._get_transition_handler(StateTransition.ENTER, TrafficLightBrokenState)
        actual_handler2 = state._get_transition_handler(StateTransition.ENTER, TrafficLightFixingState)

        self.assertEqual(expected_handler, actual_handler1)
        self.assertEqual(expected_handler, actual_handler2)

    def test_call_transition_handler_general(self):
        mock_sm = MagicMock()

        state = TrafficLightYellowState(mock_sm)
        mock_enter_func = MagicMock()
        state.enter_any = mock_enter_func

        with patch('cilantro.protocol.states.state.asyncio') as mock_asyncio:
            mock_loop = MagicMock()
            mock_loop.is_running = MagicMock(return_value=True)
            mock_asyncio.get_event_loop = MagicMock(return_value=mock_loop)

            state.call_transition_handler(StateTransition.ENTER, EmptyState)

        mock_enter_func.assert_called_once()

    def test_input_handler(self):
        mock_sm = MagicMock()
        stop_msg = RebootMessage("time to reboot")

        state = TrafficLightRedState(mock_sm)

        mock_func = MagicMock()
        state.handle_reboot_on_red = mock_func

        state.call_input_handler(message=stop_msg, input_type=StateInput.INPUT)

        mock_func.assert_called_once()

    def test_input_handler_with_args(self):
        mock_sm = MagicMock()
        mock_env = MagicMock()
        msg = ForceStopMessage("stop it guy!")

        state = TrafficLightRedState(mock_sm)

        mock_func = MagicMock(spec=state.handle_stop_msg_on_red)
        state.handle_stop_msg_on_red = mock_func

        state.call_input_handler(msg, StateInput.INPUT, envelope=mock_env)

        mock_func.assert_called_with(msg, mock_env)

    def test_input_lookup_failed_registers(self):
        mock_sm = MagicMock()
        state = TrafficLightRedState(mock_sm)

        expected_fn = state.lookup_failed
        actual_fn = state._get_status_input_handler(StateInput.LOOKUP_FAILED)

        self.assertEquals(expected_fn, actual_fn)

    def test_input_socket_added_registers_doesnt_exist(self):
        mock_sm = MagicMock()
        state = TrafficLightGreenState(mock_sm)

        expected_fn = None
        actual_fn = state._get_status_input_handler(StateInput.SOCKET_ADDED)

        self.assertEquals(expected_fn, actual_fn)

    def test_input_lookup_failed_registers_with_inheritence(self):
        mock_sm = MagicMock()
        state = TrafficLightGreenState(mock_sm)

        expected_fn = state.lookup_failed
        actual_fn = state._get_status_input_handler(StateInput.LOOKUP_FAILED)

        self.assertEquals(expected_fn, actual_fn)

    def test_input_socket_added_registers(self):
        mock_sm = MagicMock()
        state = TrafficLightYellowState(mock_sm)

        expected_fn = state.socket_added
        actual_fn = state._get_status_input_handler(StateInput.SOCKET_ADDED)

        self.assertEquals(expected_fn, actual_fn)

    def test_input_connection_dropped_registers(self):
        mock_sm = MagicMock()
        state = TrafficLightRedState(mock_sm)

        expected_fn = state.conn_dropped
        actual_fn = state._get_status_input_handler(StateInput.CONN_DROPPED)

        self.assertEquals(expected_fn, actual_fn)

    def test_call_status_input_handler(self):
        mock_sm = MagicMock()
        state = TrafficLightRedState(mock_sm)

        args = ['im an arg', 10, 'im also an arg']
        kwargs = {'dat_key': 'dat_value', 'my_fav_num': 1260}

        mock_func = MagicMock(spec=state.conn_dropped)
        state.conn_dropped = mock_func

        state.call_status_input_handler(StateInput.CONN_DROPPED, *args, **kwargs)

        mock_func.assert_called_with(*args, **kwargs)

