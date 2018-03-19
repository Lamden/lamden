from cilantro.logger import get_logger
from functools import wraps


ENTER, EXIT, RUN = 'enter', 'exit', 'run'
DEBUG_FUNCS = (ENTER, EXIT, RUN)


def receive(msg_type):
    """
    Decorator for dynamically routing incoming ZMQ messages to handles in Node's state
    """
    # TODO -- add validation to make sure @receive calls are receiving the correct message type?
    def decorate(func):
        func._recv = msg_type
        return func
    return decorate


def debug_transition(transition_type):
    def decorate(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_state = args[0]
            if transition_type == RUN:
                msg = "Running state {}".format(current_state)
            else:
                trans_state = args[1]
                msg = "Entering state {} from previous state {}" if transition_type == ENTER \
                    else "Exiting state {} to next state {}"
                msg = msg.format(current_state, trans_state)
            current_state.log.info(msg)
            return func(*args, **kwargs)
        return wrapper
    return decorate


class StateMeta(type):
    def __new__(cls, clsname, bases, clsdict):
        clsobj = super().__new__(cls, clsname, bases, clsdict)

        # Config logger
        clsobj.log = get_logger(clsname)

        # Add debug decorator to run/exit/enter methods
        for name, val in vars(clsobj).items():
            if callable(val) and name in DEBUG_FUNCS:
                # print("Setting up debug logging for name {} with val {}".format(name, val))
                setattr(clsobj, name, debug_transition(name)(val))

        # Configure @receiver registry
        clsobj._receivers = {r._recv: r for r in clsdict.values() if hasattr(r, '_recv')}
        # print("_receivers: ", clsobj._receivers)

        return clsobj


class State(metaclass=StateMeta):
    def __init__(self, state_machine=None):
        assert state_machine is not None, "Cannot create state without a pointer to its encompassing state machine"
        self.parent = state_machine

    def enter(self, prev_state):
        raise NotImplementedError

    def exit(self, next_state):
        raise NotImplementedError

    def run(self):
        raise NotImplementedError

    def __eq__(self, other):
        return type(self) == type(other)

    def __repr__(self):
        return type(self).__name__


class EmptyState(State):
    def enter(self, prev_state): pass
    def exit(self, next_state): pass
    def run(self): pass
