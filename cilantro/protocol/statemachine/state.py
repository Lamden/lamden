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

        clsobj._receivers = {}
        for r in (r for r in clsdict.values() if hasattr(r, '_recv')):
            clsobj._receivers[r._recv] = r
            subclasses = StateMeta.get_subclasses(r._recv)
            for sub in filter(lambda k: k not in clsobj._receivers, subclasses):
                clsobj._receivers[sub] = r

        print("{} has _receivers: {}".format(clsobj.__name__, clsobj._receivers))

        return clsobj

    @staticmethod
    def get_subclasses(obj_cls, subs=None) -> list:
        if subs is None:
            subs = []

        new_subs = obj_cls.__subclasses__()
        subs.extend(new_subs)
        for sub in new_subs:
            subs.extend(StateMeta.get_subclasses(sub, subs=subs))
        return subs



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
