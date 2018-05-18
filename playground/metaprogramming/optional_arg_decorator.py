class State: pass
class StateA(State): pass
class StateB(State): pass
class StateC(State): pass


ALL_STATES = 'ALL_STATES'


# def enter_state(*args):
#     def decorate(func):
#         if not states:
#             print("configuring func {} to capture all states".format(func))
#             # func._enter_handlers = states
#         else:
#             print("\nfunc {} configured to capture state {}\n".format(func, states))
#             # func._enter_handlers = states
#         func._enter_handlers = states
#
#         def _func(*args, **kwargs):
#             print("entering func with args {} and kwargs {}".format(args, kwargs))
#             func(*args, **kwargs)
#             print("exiting func")
#
#         return _func
#
#     # Check if this decorator was used with args
#     if len(args) == 1 and callable(args[0]) and not issubclass(args[0], State):
#         print("this method was not decorated")
#         states = ALL_STATES
#         return decorate(args[0])
#     else:
#         print("entry method was decorated with args {}!!!".format(args))
#         # TODO validate states are actually state subclasses
#         states = args
#         return decorate

def enter_state(*args):
    return _transition_state(handlers_attr='_entry_handlers', args=args)


def _transition_state(handlers_attr: str, args):
    def decorate(func):
            if not states:
                print("configuring func {} to capture all states".format(func))
                # func._enter_handlers = states
            else:
                print("\nfunc {} configured to capture state {}\n".format(func, states))
                # func._enter_handlers = states

            # func._enter_handlers = states
            print("setting attr named {} on object {} to value {}".format(handlers_attr, func, states))
            setattr(func, handlers_attr, states)

            def _func(*args, **kwargs):
                print("entering func with args {} and kwargs {}".format(args, kwargs))
                func(*args, **kwargs)
                print("exiting func")

            return _func

    # Check if this decorator was used with args
    if len(args) == 1 and callable(args[0]) and not issubclass(args[0], State):
        print("this method was not decorated")
        states = ALL_STATES
        return decorate(args[0])
    else:
        print("entry method was decorated with args {}!!!".format(args))
        # TODO validate states are actually state subclasses
        states = args
        return decorate


class Tester:
    @enter_state(StateA)
    def do_something(thing='code', other_thing='sleep'):
        print("doing {} with other thing {}".format(thing, other_thing))


# do_something(thing='play', other_thing='blay')

# print(do_something._entry_handlers)
if __name__ == '__main__':
    t = Tester()
    # print(t.do_something._entry_handlers)
