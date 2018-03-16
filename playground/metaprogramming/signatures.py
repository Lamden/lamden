from inspect import Parameter, Signature
from cilantro.logger import get_logger
"""
First, just validate cmd
Then validate kwargs using signatures in the appropriate subclass

"""


class TestMeta(type):
    pass


class Test(metaclass=TestMeta):
    socket_fields = ('pub_sockets', 'sub_sockets', 'req_sockets')


class CommandMeta(type):
    def __new__(cls, clsname, bases, clsdict):
        print("CommandMeta NEW called /w class ", clsname)
        clsobj = super().__new__(cls, clsname, bases, clsdict)

        if not hasattr(clsobj, 'registry'):
            print("Creating Registry")
            clsobj.registry = {}

        clsobj.log = get_logger(clsobj.__name__)

        print("Adding to registry: ", clsobj.__name__)
        clsobj.registry[clsobj.__name__] = clsobj

        return clsobj


class Command(metaclass=CommandMeta):
    pass


class AddSubCommand(Command):
    @classmethod
    def execute(cls, url, callback):
        print("add sub EXECUTE")
        print('url: ', url)
        print('callback: ', callback)


class RemoveSubCommand(Command):
    @classmethod
    def execute(cls, url):
        print("remove sub EXECUTE")
        print('url: ', url)

# class CommandSignature:
#     def __init__(self, cmd, **kwargs):
#         self.cmd = cmd
#         self.kwargs = kwargs


# def make_signature(names):
#     return Signature(
#         Parameter(name, Parameter.POSITIONAL_OR_KEYWORD)
#         for name in names)
#
# class CommandMeta(type):
#     def __new__(cls, clsname, bases, clsdict):
#         print("CommandMeta NEW called /w class ", clsname)
#         clsobj = super().__new__(cls, clsname, bases, clsdict)
#
#         sig = make_signature(clsobj._fields)
#         setattr(clsobj, '__signature__', sig)
#         setattr(clsobj, 'execute.__signature__', sig)
#
#         if not hasattr(clsobj, 'registry'):
#             print("Creating Registry")
#             clsobj.registry = {}
#         print("Adding to registry: ", clsobj.__name__)
#         clsobj.registry[clsobj.__name__] = clsobj
#
#         return clsobj
#
#
# class Command(metaclass=CommandMeta):
#     _fields = []
#     def __init__(self, *args, **kwargs):
#         bound = self.__signature__.bind(*args, **kwargs)
#         for name, val in bound.arguments.items():
#             setattr(self, name, val)
#
#
# class AddSubCommand(Command):
#     _fields = ['url', 'callback']
#
#     @classmethod
#     def execute(cls, url, callback):
#         print('url: ', url)
#         print('callback: ', callback)
#
# class RemoveSubCommand(Command):
#     _fields = ['url']




# class RegisterLeafClasses(type):
#     # def __init__(cls, name, bases, nmspc):
#     #     print("RegisterLeafClasses init called /w class ", cls.__name__)
#     #     super(RegisterLeafClasses, cls).__init__(name, bases, nmspc)
#     #     if not hasattr(cls, 'registry'):
#     #         print("Creating Registry")
#     #         cls.registry = set()
#     #     print("Adding to registry: ", cls.__name__)
#     #     cls.registry.add(cls)
#     #     print("Removing from registry: {}".format([c for c in bases]))
#     #     cls.registry -= set(bases) # Remove base classes
#
#     def __new__(cls, clsname, bases, clsdict):
#         print("RegisterLeafClasses NEW called /w class ", cls.__name__)
#         clsobj = super().__new__(cls, clsname, bases, clsdict)
#
#         if not hasattr(clsobj, 'registry'):
#             print("Creating Registry")
#             clsobj.registry = {}
#         print("Adding to registry: ", clsobj.__name__)
#         clsobj.registry[clsobj.__name__] = clsobj # ok does thsi need to happen in init? whats clsobj? can it get me the class
#         # print("Removing from registry: {}".format([c for c in bases]))
#         # clsobj.registry -= set(bases) # Remove base classes
#
#         return clsobj
#
#     # def __new__(cls, clsname, bases, clsdict):
#     #     clsobj = super().__new__(cls, clsname, bases, clsdict)
#     #     if not hasattr(clsobj, 'registry'):
#     #         clsobj.registry = set()
#     #         clsobj.registry.add(cls)
#     #         clsobj.registry -= set(bases)
#     # Metamethods, called on class objects:
#     def __iter__(cls):
#         return iter(cls.registry)
#     def __str__(cls):
#         if cls in cls.registry:
#             return cls.__name__
#         return cls.__name__ + ": " + ", ".join([sc.__name__ for sc in cls])
#
# class Color(metaclass=RegisterLeafClasses):
#     pass
#
# class Red(Color):
#     @classmethod
#     def do_this(cls):
#         print("im doing this on cls ", cls.__name__)