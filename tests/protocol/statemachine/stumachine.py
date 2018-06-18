from cilantro.protocol.statemachine import *


"""
This stuff is a little tricky to test. In interest of optimizing utility per unit of time, we just create a toy example 
StateMachine class, with toy states, and use this in our test cases. So these are more like state machine integration
tests than unit tests.  

The proper way to do this would prolly be to mock all this stuff, but that would be hella tedious and quite fragile.  
"""


DEFAULT_LIFT = None
DEFAULT_WEIGHT = 0
DEFAULT_SLEEP_TIME = 8

class StuMachine(StateMachine): pass


class LiftingTimeMessage:
    def __init__(self, weight, lift):
        self.weight = weight
        self.lift = lift

class GoToSleepMessage:
    def __init__(self, sleep_time=DEFAULT_SLEEP_TIME):
        self.sleep_time = sleep_time


@StuMachine.register_init_state
class SleepState(State):
    def reset_attrs(self):
        self.did_enter = False
        self.sleep_time = DEFAULT_SLEEP_TIME

    @input(LiftingTimeMessage)
    def handle_lifting_message(self, msg: LiftingTimeMessage):
        self.log.debug("Got lifting msg ... transitioning to lift state")
        self.parent.transition("LiftState", lift=msg.lift, weight=msg.weight)

    @enter_from_any
    def enter_general(self, prev_state, sleep_time = DEFAULT_SLEEP_TIME):
        self.log.debug("general entry from prev state {}".format(prev_state))
        self.sleep_time = sleep_time
        self.did_enter = True

    @exit_to_any
    def exit_any(self, next_state):
        self.parent.sleep_did_exit_any = True


@StuMachine.register_state
class CodeState(State):
    def reset_attrs(self):
        self.lang = None
        self.activity = None

    # If the StuMachine tries to code first thing in the morn before lifting he goes back to sleep
    @enter_from(SleepState)
    def enter_from_sleep(self, prev_state):
        assert prev_state is SleepState, "wtf prev_state is not sleep state .... ?"

        self.log.debug("Entering CodeState from sleep state. Nah. Going back to bed.")
        self.parent.transition(SleepState)

    @enter_from_any
    def enter_general(self, prev_state):
        self.log.debug("general entry from prev state {}".format(prev_state))


@StuMachine.register_state
class LiftState(State):
    BENCH, SQUAT, DEADLIFT = 'BENCH', 'SQUAT', 'DEAD LIFT'

    def reset_attrs(self):
        self.current_lift = DEFAULT_LIFT
        self.current_weight = DEFAULT_WEIGHT

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

    @exit_to(SleepState)
    def exit_to_sleep(self, next_state):
        self.log.debug("exiting lift state to sleep state")
        self.parent.exit_lift_to_sleep_called = True

    def lift(self):
        self.log.debug("Doing lift: {} ... with weight: {}".format(self.current_lift, self.current_weight))


@StuMachine.register_state
class FactorioState(State):

    def reset_attrs(self):
        pass

    @timeout_after(1.0)
    def stop_playing(self):
        self.log.debug("ay im done dancing...let go to chill state")
        self.parent.transition('ChillState')


@StuMachine.register_state
class ChillState(State):

    def reset_attrs(self):
        pass

    @enter_from_any
    def enter_any(self, prev_state):
        self.log.debug("boy im chilling. Before I was chilling, I was in doing state: <{}>".format(prev_state))