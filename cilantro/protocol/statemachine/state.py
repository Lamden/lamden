from cilantro.logger import get_logger
from functools import wraps


ENTER, EXIT, RUN = 'enter', 'exit', 'run'
DEBUG_FUNCS = (ENTER, EXIT, RUN)


def recv(msg_type):
    """
    Decorator for dynamically routing incoming ZMQ messages to handles in Node's state
    """
    # TODO -- add validation to make sure @receive calls are receiving the correct message type?
    def decorate(func):
        func._recv = msg_type
        return func
    return decorate


# TODO -- possibly add another arg for replying to different senders in different ways
def recv_req(msg_type):
    def decorate(func):
        func._reply = msg_type
        return func
    return decorate


def timeout(msg_type):
    def decorate(func):
        func._timeout = msg_type
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
                setattr(clsobj, name, debug_transition(name)(val))

        # Configure decorator callback registries
        clsobj._receivers = {r._recv: r for r in clsdict.values() if hasattr(r, '_recv')}
        clsobj._repliers = {r._reply: r for r in clsdict.values() if hasattr(r, '_reply')}
        clsobj._timeouts = {r._timeout: r for r in clsdict.values() if hasattr(r, '_timeout')}

        return clsobj


class State(metaclass=StateMeta):
    def __init__(self, state_machine):
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
