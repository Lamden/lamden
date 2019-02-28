from cilantro_ee.protocol.states.state import State
from cilantro_ee.protocol.states.decorators import exit_to, exit_to_any, enter_from_any, timeout_after, enter_from, \
    input_request, input, input_connection_dropped, input_socket_connected, input_lookup_failed

YELLOW_TIMEOUT_DUR = 1.0


class Message:
    def __init__(self, msg):
        self.msg = msg

    def __repr__(self):
        return self.msg


class ForceStopMessage(Message): pass
class RebootMessage(Message): pass
class StatusRequest(Message): pass
class MysteriousMessage(Message): pass

class TrafficLightBrokenState(State): pass
class TrafficLightFixingState(State): pass


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

    @input_lookup_failed
    def lookup_failed(self, vk, *args, **kwargs):
        self.log.debug("lookup failed for vk {} with args {} and kwargs {}".format(vk, args, kwargs))

    def reset_attrs(self):
        pass


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

    @input_lookup_failed
    def lookup_failed(self, vk, *args, **kwargs):
        self.log.debug("lookup failed for vk {} with args {} and kwargs {}".format(vk, args, kwargs))

    # Uncomment this and confirm it raises an assertion when any tests are run
    # @enter_from_any
    # def enter_general_dupe(self, prev_state):
    #     pass

    @exit_to_any
    def exit_general(self, next_state):
        pass

    @input_connection_dropped
    def conn_dropped(self, *args, **kwargs):
        self.log.debug("Connection dropped with args {} and kwargs {}".format(args, kwargs))

    # @exit_to(TrafficLightBrokenState, TrafficLightFixingState)
    @exit_to("TrafficLightBrokenState", "TrafficLightFixingState")
    def exit_from_maintenance(self, next_state):
        pass

    # Uncomment this and confirm it raises an assertion when any tests are run
    # @exit_from_any
    # def exit_general_dupe(self, prev_state):
    #     pass


class TrafficLightYellowState(TrafficLightBaseState):

    @timeout_after(YELLOW_TIMEOUT_DUR)
    def timeout(self):
        self.log.critical("yellow light timed out!!!")

    @input(ForceStopMessage)
    def handle_stop_msg_on_yellow(self, msg: ForceStopMessage):
        pass

    # @enter_from(TrafficLightRedState)
    @enter_from("TrafficLightRedState")
    def enter_from_red(self, prev_state):
        pass

    @enter_from(TrafficLightBrokenState, TrafficLightFixingState)
    # @enter_from("TrafficLightBrokenState", "TrafficLightFixingState")
    def enter_from_broken_or_fixing(self, prev_state):
        pass

    @enter_from_any
    def enter_any(self, prev_state):
        self.log.debug("entering from any from prev state {}".format(prev_state))

    @input_socket_connected
    def socket_added(self, *args, **kwargs):
        self.log.debug("Socket added with args {} and kwargs {}".format(args, kwargs))

    # UNCOMMENT THIS AND VERIFY AN ASSERTION IS THROWN WHEN ANY TEST IS RUN
    # @enter_from(TrafficLightBrokenState)
    # def this_should_blow_up_cause_another_handler_for_that_state_already_exists(self):
    #     pass


class TrafficLightGreenState(TrafficLightBaseState):
    @input_request(StatusRequest)
    def handle_status_req_on_green(self, request: StatusRequest, envelope):
        self.request = request
