"""
would like a way to hijack reactor logic and set a timeout for selected zmq events, such as recv,
sends, ect

Can we slap a decorator on top of ZMQ ... so we can modify send and recv calls...?

we could mess with the router tho, so stuff only goes thru sometimes...this is likely easiest
so it should be somewhat trivial to use metaclass the basenode to alter the behavior or recv...but what
about send? Would we separately how to metaclass the reactor? Or can we reach into NodeBase and modify
calls on the reactor

- build nondeterministic skip list of hashes on top of block chain
- could connections to nodes in skip list be difference between rolling hashes?
- or does each pair of transactions need 2 co-created r.h.
Will guarantee traversals in lg(n) times where n is the # of blocks

"""
from cilantro.nodes import NodeBase
from cilantro.protocol.reactor import NetworkReactor, ReactorCore
from cilantro.logger import get_logger
from functools import wraps
import random

P = 0.8

def do_nothing(*args, **kwargs):
    print("!!! DOING NOTHING !!!\nargs: {}\n**kwargs: {}".format(args, kwargs))

def sketchy_execute(prob_fail):
    def decorate(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # print("UR BOY HAS INJECTED A SKETCH EXECUTE FUNC LOL LFG")
            if random.random() < prob_fail:
                print("!!! not running func")
                return do_nothing(*args, **kwargs)
            else:
                # print("running func")
                return func(*args, **kwargs)
        return wrapper
    return decorate

class RogueMeta(type):
    _OVERWRITES = ('route', 'route_req', 'route_timeout')

    def __new__(cls, clsname, bases, clsdict):
        clsobj = super().__new__(cls, clsname, bases, clsdict)

        print("Rogue meta created with class name: ", clsname)
        print("bases: ", bases)
        print("clsdict: ", clsdict)
        print("dir: ", dir(clsobj))

        for name in dir(clsdict):
            if name in cls._OVERWRITES:
                print("\n\n***replacing {} with sketchy executor".format(name))
                setattr(clsobj, name, sketchy_execute(P)(getattr(clsobj, name)))

        return clsobj

if __name__ == "__main__":
    pass

# class RogueNode(NodeBase):
#
#     def __init__(self, url=None, signing_key=None):
#         super().__init__(url, signing_key)
#         self.reactor.reactor.execute_cmd = sketchy_execute(0.8)(self.reactor.execute_cmd)

