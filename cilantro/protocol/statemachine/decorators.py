

class StateInput:
    """
    A grouping of constants
    """
    INPUT = '_route_input'
    REQUEST = '_route_request'
    TIMEOUT = '_route_timeout'

    ALL = [INPUT, REQUEST, TIMEOUT]


"""
----------------------------------------
Input Decorators
----------------------------------------

Input decorators allow states to define logic for incoming messages from the ReactorDaemon. These messages can be
envelopes from other actors, or timeout callbacks from unreceived replies.

# TODO more explanations
# TODO examples of how to use input decorators
"""

def input(msg_type):
    def decorate(func):
        # func._recv = msg_type
        setattr(func, StateInput.INPUT, msg_type)
        return func
    return decorate


def input_request(msg_type):
    def decorate(func):
        # func._reply = msg_type
        setattr(func, StateInput.REQUEST, msg_type)
        return func
    return decorate


def timeout(msg_type):
    def decorate(func):
        # func._timeout = msg_type
        setattr(func, StateInput.TIMEOUT, msg_type)
        return func
    return decorate


"""
----------------------------------------
Transition Decorators
----------------------------------------

Transition decorators allow states to define logic surrounding state transitions. Methods can be decorated to execute
some code whenever the defining state is transition into from another state, using enter_state(...), or transitioned 
out of into another state, using exit_state(....).  

For either decorator enter_state(...)/exit_state(...), if no arguement is specified then that method will act as a 
'wildcard' and be called for ALL transitions, unless the state has another method that is decorated to handle a
a particular state.

# TODO clearer explanation
# TODO examples 
"""


def enter_state(prev_state=None):
    pass


def exit_state(next_state=None):
    pass