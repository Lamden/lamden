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


class TrafficLightBaseState(State):
    @input(ForceStopMessage)
    def handle_stop_msg(self, msg: ForceStopMessage):
        self.log.debug("got force stop msg: {}".format(msg))


class TrafficLightRedState(State):
    pass


class TrafficLightYellowState(State):
    pass


class TrafficLightGreenState(State):
    pass


STATES = [TrafficLightGreenState, TrafficLightRedState, TrafficLightYellowState]


class StateTest(TestCase):

    # def setUp(self):
    #     self.states = []
    #     for
    #
    # def tearDown(self):
    #     self.states = []

    def test_get_input_handler_with_input(self):
        """
        Tests _get_input_handler with input type StateInput.INPUT
        """
        mock_sm = MagicMock()
        stop_msg = ForceStopMessage("stop it guy")

        state = TrafficLightBaseState(mock_sm)

        expected_handler = state.handle_stop_msg
        # actual_handler = state._receivers[ForceStopMessage]
        actual_handler = state._get_input_handler(stop_msg, StateInput.INPUT)

        self.assertEqual(expected_handler, actual_handler)
