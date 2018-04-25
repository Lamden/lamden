import asyncio
import zmq.asyncio


"""
Subclass of zmq.asyncio.Socket to nicely plug into an event loop and handle serialization/deserialization/validation
of messages over that socket under the hood.
"""

# class ReactorContext(zmq.asyncio.Context):
#     @property
#     def _socket_class(self):
#         return ReactorSocketBase
#
# class ReactorSocketBase(zmq.asyncio.Socket):
#
#     def __init__(self, loop, socket_type, *args, **kwargs):
#         super().__init__(socket_type=socket_type, *args, **kwargs)
#         self.loop = loop
#
#     @classmethod
#     def create(cls, context: zmq.asyncio.Context, loop: asyncio.BaseEventLoop, socket_type, *args, **kwargs):
#         # context._socket_class = ReactorSocketBase
#         return context.socket(socket_type=socket_type)
#
#
#
#
#
# class ReactorInterfaceSocket(ReactorSocketBase):
#     def __init__(self, loop, *args, **kwargs):
#         super().
