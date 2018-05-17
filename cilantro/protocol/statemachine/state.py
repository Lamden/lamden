from cilantro.logger import get_logger
from functools import wraps


ENTER, EXIT, RUN = 'enter', 'exit', 'run'
DEBUG_FUNCS = (ENTER, EXIT, RUN)


def debug_transition(transition_type):
    """
    Decorator to magically log any transitions on StateMachines
    """
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

                other_args = args[2:]
                if len(other_args) > 0 or len(kwargs) > 0:
                    msg += "... with additional args = {}, kwargs = {}".format(other_args, kwargs)

            current_state.log.info(msg)
            return func(*args, **kwargs)
        return wrapper
    return decorate


class StateMeta(type):
    """
    Metaclass to register state receivers.
    """
    def __new__(cls, clsname, bases, clsdict):
        clsobj = super().__new__(cls, clsname, bases, clsdict)
        clsobj.log = get_logger(clsname)

        # Add debug decorator to run/exit/enter methods
        for name, val in vars(clsobj).items():
            if callable(val) and name in DEBUG_FUNCS:
                # print("Setting up debug logging for name {} with val {}".format(name, val))
                setattr(clsobj, name, debug_transition(name)(val))

        # Configure receivers, repliers, and timeouts
        clsobj._receivers = {}

        for r in dir(clsobj):
            func = getattr(clsobj, r)
            if hasattr(func, '_recv'):
                clsobj._receivers[func._recv] = func
                subclasses = StateMeta._get_subclasses(func._recv)
                for sub in filter(lambda k: k not in clsobj._receivers, subclasses):
                    clsobj._receivers[sub] = func

        # print("{} has _receivers: {}".format(clsobj.__name__, clsobj._receivers))

        # TODO -- config repliers and timeouts to support polymorphism as well
        clsobj._repliers = {r._reply: r for r in clsdict.values() if hasattr(r, '_reply')}
        clsobj._timeouts = {r._timeout: r for r in clsdict.values() if hasattr(r, '_timeout')}

        return clsobj

    @staticmethod
    def _get_subclasses(obj_cls, subs=None) -> list:
        if subs is None:
            subs = []

        new_subs = obj_cls.__subclasses__()
        subs.extend(new_subs)
        for sub in new_subs:
            subs.extend(StateMeta._get_subclasses(sub, subs=subs))

        return subs


class State(metaclass=StateMeta):
    def __init__(self, state_machine):
        self.parent = state_machine
        self.reset_attrs()

    def reset_attrs(self):
        pass

    def enter(self, prev_state, *args, **kwargs):
        pass

    def exit(self, next_state, *args, **kwargs):
        pass

    def run(self):
        pass

    def __eq__(self, other):
        return type(self) == type(other)

    def __repr__(self):
        return type(self).__name__


class EmptyState(State):
    def enter(self, prev_state): pass
    def exit(self, next_state): pass
    def run(self): pass
