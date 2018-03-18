"""
Node should be able to define routes using decorators to handle incoming messages, ie something like
@recieve(Transaction):
def recv_transaction(self, tx):
    ...

An implementation is needed for every possible message type a node can receive.

- Node extends some base class that handles networking events (ie. NetworkReactor, or some augmentation of it)
- Metaclass will dynamically setup hooks for receiving these networking events and routing the to appropriate decorators

Should there be a "routing" object, or even config file where the network topology for a node is defined staticly?
Or should this just be implicit in the setup of a node.


ATTACK PLAN
use decorators and metaclasses to
    - create a class that can define a decorator taking 1 arg
    - these decorators get registered in the metaclass with their arg
    - this metaclass registry dictionary should be different for direct descendants of the metaclass

To hookup to decorators and metaclass, this means either
A) The decorator must have a reference to the class, object, or metaclass
B) The metaclass must search for all decorators during its instantiation (its creation would be too early I think)

"""
from cilantro.logger import get_logger
from functools import wraps, partial
from collections import OrderedDict


class MessageMeta(type):
    # @classmethod
    # def __prepare__(cls, name, bases):
    #     print("__prepare called for cls name: ", name)
    #     return OrderedDict()

    def __new__(cls, clsname, bases, clsdict):
        print("MessageMeta NEW called /w class ", clsname)
        clsobj = super().__new__(cls, clsname, bases, clsdict)
        if not hasattr(clsobj, 'registry'):
            print("Creating Registry")
            clsobj.registry = {}

        print("Adding to registry: ", clsobj)

        # Make an "undirected" mapping between classes and their enum vals
        l = len(clsobj.registry) // 2
        clsobj.registry[clsobj] = l
        clsobj.registry[l] = clsobj

        return clsobj

    # def __init__(cls, name, bases, nmspc):
    #     print("__init__ called on name: ", name)
    #     print("namespace: ", nmspc)
    #     super().__init__(name, bases, nmspc)


class MessageBase(metaclass=MessageMeta):
    def __init__(self, msg=''): self.msg = msg
    def __repr__(self): return self.msg
class PokeMessage(MessageBase): pass
class RequestMessage(MessageBase): pass
class NotifyMessage(MessageBase): pass


def debug(func):
    '''
    A simple debugging decorator
    '''
    msg = func.__qualname__
    @wraps(func)
    def wrapper(*args, **kwargs):
        print(msg)
        return func(*args, **kwargs)
    return wrapper

def debugargs(prefix=''):
    '''
    A debugging decorator that takes arguments
    '''
    def decorate(func):
        msg = prefix + func.__qualname__
        @wraps(func)
        def wrapper(*args, **kwargs):
            print(msg)
            return func(*args, **kwargs)
        return wrapper
    return decorate

def receive(msg_type):
    print("INSIDE RECIEVE DECORATOR")
    def decorate(func):
        print("INSIDE RECIEVE DECORATE WITH FUNC ", func)
        func._receiver_type = msg_type
        return func
    return decorate

class MetaRoute(type):
    def __new__(cls, clsname, bases, clsdict):
        print("-- MetaRoute New called on...")
        print("cls.__name__ = ", clsname)
        print("clsname = ", clsname)
        print("bases = ", bases)
        print("clsdict = ", clsdict)

        clsobj = super().__new__(cls, clsname, bases, clsdict)
        print("Creating clsobj: ", clsobj)

        clsobj.log = get_logger(clsobj.__name__)
        clsobj._receivers = {r._receiver_type: r for r in clsdict.values() if hasattr(r, '_receiver_type')}
        print("_receivers: ", clsobj._receivers)

        return clsobj


class RouterBase(metaclass=MetaRoute):

    def route(self, msg):
        print("routing message: {}".format(msg))
        print("receivers: {}".format(self._receivers))
        print("registery: {}".format(MessageBase.registry))

        msg_type = type(msg)

        if msg_type in self._receivers:
            print("Msg type {} in receivers!!".format(msg_type))
            self._receivers[msg_type](self, msg)
            # self._receivers
        else:
            print("!! Unimplemented message type received: {}".format(msg_type))


class Router(RouterBase):

    @receive(PokeMessage)
    def recv_poke(self, poke):
        self.log.critical("Handling poke! {}".format(poke))

    @receive(NotifyMessage)
    def recv_notify(self, notif):
        self.log.critical("Handling notif! {}".format(notif))


class RouterB(RouterBase):
    @receive(PokeMessage)
    def handle_poke(self, poke):
        self.log.critical("i'm doing somthing diff with this poke! {}".format(poke))


