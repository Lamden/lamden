from cilantro_ee.logger import get_logger
from cilantro_ee.messages.envelope.envelope import Envelope
from cilantro_ee.protocol.structures.capped_containers import CappedSet
import traceback
from cilantro_ee.protocol.states.state import StateInput
from cilantro_ee.constants.protocol import DUPE_TABLE_SIZE
import asyncio

from typing import Union
import types


# Internal constants (used as keys)
_SOCKET = 'socket'
_HANDLER = 'handler'


class ExecutorMeta(type):
    def __new__(cls, clsname, bases, clsdict):
        clsobj = super().__new__(cls, clsname, bases, clsdict)
        # clsobj.log = get_logger(clsobj.__name__)

        if not hasattr(clsobj, 'registry'):
            clsobj.registry = {}

        if clsobj.__name__ != 'ExecutorBase':  # Exclude ExecutorBase base class
            clsobj.registry[clsobj.__name__] = clsobj

        return clsobj


class ExecutorBase(metaclass=ExecutorMeta):

    _recently_seen = CappedSet(max_size=DUPE_TABLE_SIZE)
    _parent_name = 'ReactorDaemon'  # used for log names

    def __init__(self, loop, context, router):
        self.router = router
        self.loop = loop
        asyncio.set_event_loop(self.loop)  # not sure if this is necessary -- davis

        self.context = context
        self.log = get_logger("{}".format(type(self).__name__))

    def add_listener(self, listener_fn, *args, **kwargs):
        # listener_fn must be a coro
        self.log.info("add_listener scheduling future {} with args {} and kwargs {}".format(listener_fn, args, kwargs))
        return asyncio.ensure_future(self._listen(listener_fn, *args, **kwargs))

    async def _listen(self, listener_fn, *args, **kwargs):
        self.log.debugv("_listen called with fn {}, and args={}, kwargs={}".format(listener_fn, args, kwargs))

        try:
            await listener_fn(*args, **kwargs)
        except Exception as e:
            delim_line = '!' * 64
            err_msg = '\n\n' + delim_line + '\n' + delim_line
            err_msg += '\n ERROR CAUGHT IN LISTENER FUNCTION {}\ncalled \w args={}\nand kwargs={}\n'\
                        .format(listener_fn, args, kwargs)
            err_msg += '\nError Message: '
            err_msg += '\n\n{}'.format(traceback.format_exc())
            err_msg += '\n' + delim_line + '\n' + delim_line + '\n'
            self.log.error(err_msg)

    async def recv_env_multipart(self, socket, callback_fn: types.MethodType, ignore_first_frame=False):
        self.log.socket("--- Starting recv on socket {} with callback_fn {} ---".format(socket, callback_fn))
        while True:
            self.log.spam("waiting for multipart msg...")
            try:
                msg = await socket.recv_multipart()
            except asyncio.CancelledError:
                self.log.info("Socket cancelled: {}".format(socket))
                socket.close()
                break

            self.log.spam("Got multipart msg: {}".format(msg))

            if ignore_first_frame:
                header = None
            else:
                assert len(msg) == 2, "Expected 2 frames (header, envelope) but got {}".format(msg)
                header = msg[0].decode()

            env_binary = msg[-1]
            env = self._validate_envelope(envelope_binary=env_binary, header=header)

            if not env:
                continue

            ExecutorBase._recently_seen.add(env.meta.uuid)
            callback_fn(header=header, envelope=env)

    def notify_socket_connected(self, socket_type: int, vk: str, url: str):
        self.router.route_callback(callback=StateInput.SOCKET_CONNECTED, socket_type=socket_type, vk=vk, url=url)

    def _validate_envelope(self, envelope_binary: bytes, header: str) -> Union[None, Envelope]:
        # TODO return/raise custom exceptions in this instead of just logging stuff and returning none

        # Deserialize envelope
        env = None
        try:
            env = Envelope.from_bytes(envelope_binary)
        except Exception as e:
            self.log.error("Error deserializing envelope: {}".format(e))
            return None

        # Check seal
        if not env.verify_seal():
            self.log.error("Seal could not be verified for envelope {}".format(env))
            return None

        # If header is not none (meaning this is a ROUTE msg with an ID frame), then verify that the ID frame is
        # the same as the vk on the seal

        # TODO add this code back in appropriately...
        # if header and (header != env.seal.verifying_key):
        #     self.log.error("Header frame {} does not match seal's vk {}\nfor envelope {}"
        #                    .format(header, env.seal.verifying_key, env))
        #     return None

        # Make sure we haven't seen this message before
        if env.meta.uuid in ExecutorBase._recently_seen:
            self.log.debug("Duplicate envelope detect with UUID {}. Ignoring.".format(env.meta.uuid))
            return None

        # TODO -- checks timestamp to ensure this envelope is recv'd in a somewhat reasonable time (within N seconds)

        # If none of the above checks above return None, this envelope should be good
        return env

    def teardown(self):
        raise NotImplementedError



