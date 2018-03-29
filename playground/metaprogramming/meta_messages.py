"""

"""
class MessageMeta(type):
    def __new__(cls, clsname, bases, clsdict):
        print("MessageMeta NEW called /w class ", clsname)
        clsobj = super().__new__(cls, clsname, bases, clsdict)

        if not hasattr(clsobj, 'registry'):
            # print("Creating Registry")
            clsobj.registry = {}
        # print("Adding to registry: ", clsobj.__name__)
        clsobj.registry[clsobj.__name__] = clsobj

        return clsobj

class MessageBase(metaclass=MessageMeta): pass


class PokeMessage(MessageBase): pass


class RequestMessage(MessageBase): pass


class NotifyMessage(MessageBase): pass