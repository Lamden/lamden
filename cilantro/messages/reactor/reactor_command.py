from cilantro.utils import lazy_property
from cilantro.messages import MessageBase, Envelope

import capnp
import reactor_capnp


# We create convenience properties for commonly used fields on ReactorCommands,
CLS_NAME = 'class_name'
FN_NAME = 'func_name'
CALLB = 'callback'
HEADER = 'header'


class ReactorCommand(MessageBase):
    """
    ReactorCommand defines a data serialization format for messages passed over inproc PAIR
    sockets between ReactorInterface (on the main proc), and ReactorDaemon (on daemon)

    Messages from ReactorInterface --> ReactorDaemon are nicknamed "commands", since they specify the
    executor name/function/kwargs that ReactorDaemon should run.
    This includes required fields 'class_name' and 'func_name'. Commands which compose data over the
    wire (i.e. pub, request, reply) must have the envelope arg specified as a valid Envelope instance.

    Messages from ReactorDaemon --> ReactorInterface are nicknamed "callbacks", since they specify
    some callback on the StateMachine as a function of incoming data.
    All callbacks have a 'callback' field which is a string denoting the callback function on the router.
    All callback excepts timeouts will have an 'envelope' property, which correspondes to the serialized Envelope capnp
    data received from the outside world.
    """

    def validate(self):
        # TODO -- implement
        pass

    @classmethod
    def _deserialize_data(cls, data: bytes):
        return reactor_capnp.ReactorCommand.from_bytes_packed(data)

    @classmethod
    def create_cmd(cls, class_name: str, func_name: str, envelope: Envelope=None, **kwargs):
        kwargs[CLS_NAME] = class_name
        kwargs[FN_NAME] = func_name
        return cls.create(envelope=envelope, **kwargs)

    @classmethod
    def create_callback(cls, callback: str, envelope: Envelope=None, envelope_binary: bytes=None, **kwargs):
        # TODO -- simplify API for command creation process
        kwargs[CALLB] = callback
        return cls.create(envelope=envelope, envelope_binary=envelope_binary, **kwargs)

    @classmethod
    def create(cls, envelope: Envelope=None, envelope_binary: bytes=None, **kwargs):
        assert not (envelope and envelope_binary), "Either envelope or envelope_binary should be passed in (not both)"

        cmd = reactor_capnp.ReactorCommand.new_message()

        if envelope:
            assert isinstance(envelope, Envelope), "'envelope' kwarg must be an Envelope instance"
            cmd.envelope.data = envelope.serialize()
        if envelope_binary:
            assert isinstance(envelope_binary, bytes), "'envelope_binary' must be bytes"
            cmd.envelope.data = envelope_binary

        cmd.init('kwargs', len(kwargs))
        for i, key in enumerate(kwargs):
            cmd.kwargs[i].key, cmd.kwargs[i].value = str(key), str(kwargs[key])

        return cls.from_data(cmd)

    @lazy_property
    def envelope(self):
        if self._data.envelope.which() == 'unset':
            return None
        else:
            return Envelope.from_bytes(self._data.envelope.data)

    @lazy_property
    def envelope_binary(self):
        if self._data.envelope.which() == 'unset':
            return None
        else:
            return self._data.envelope.data

    @lazy_property
    def kwargs(self):
        return {arg.key: arg.value for arg in self._data.kwargs}

    @property
    def class_name(self):
        return self.kwargs.get(CLS_NAME)

    @property
    def func_name(self):
        return self.kwargs.get(FN_NAME)

    @property
    def callback(self):
        return self.kwargs.get(CALLB)

    @property
    def header(self):
        return self.kwargs.get(HEADER)

    def __eq__(self, other):
        my_kwargs, other_kwargs = self.kwargs, other.kwargs
        # manually copy envelope binary to kwaargs for comparison
        my_kwargs['env_bin'], other_kwargs['env_bin'] = self.envelope_binary, other.envelope_binary
        return self.kwargs == other.kwargs
